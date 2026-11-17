// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

/// Root Anchor (RA) of AMTP: stores (e*_i, R*_Di) per domain and the Global Root R*_G.
///
/// A new Domain Root is accepted only if, atomically,
///   * the predecessor is the current anchored root,
///   * the epoch is exactly e* + 1, and
///   * the domain's root-update key signed the transition (σ_root).
/// R*_G is then recomputed over all current Domain Roots. Only roots go on-chain.
///
/// Hashes match amtp_code/amtp/core/hashing.py and core/merkle.py byte for byte:
///   H(p1, p2, ...) = SHA-256(len(p1) ‖ p1 ‖ len(p2) ‖ p2 ...), 4-byte big-endian lengths,
///   uint = 8-byte big-endian; Merkle leaf H(0x00 ‖ v), node H(0x01 ‖ l ‖ r), padding H(0x02).
/// σ_root: secp256k1 ECDSA (EIP-191 "personal" message) over
///   SHA-256(transition_message ‖ chainid (8 bytes) ‖ this contract (20 bytes)),
///   transition_message = lp("AMTP/transition/v1", domain, e', R^(e*), R^(e'), Δ)  (anchor.py).
/// ECDSA stands in for ABS, as Ed25519 does in the in-process anchor.
contract RootAnchor {
    struct Domain {
        address owner;    // root-update key of the domain (Setup, eq. 1)
        uint64 epoch;     // e*
        bytes32 root;     // R*_D
        bool registered;
    }

    bytes constant TAG_TRANSITION = "AMTP/transition/v1";
    uint256 constant MAX_DOMAINS = 64;
    // secp256k1 order / 2: signatures with a larger s are rejected (no malleable copies)
    uint256 constant HALF_N = 0x7FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF5D576E7357A4501DDFE92F46681B20A0;

    address public immutable admin;
    mapping(bytes32 => Domain) private domains;   // keccak256(domain name) -> state
    bytes[] private names;                         // registered domain names, sorted (bytes order)
    bytes32 public globalRoot;                     // R*_G

    event Registered(bytes domain, address owner, bytes32 root, bytes32 globalRoot);
    event Anchored(bytes domain, uint64 epoch, bytes32 prev, bytes32 root, bytes32 delta, bytes32 globalRoot);

    constructor() {
        admin = msg.sender;
        globalRoot = _merkleRoot(new bytes32[](0));
    }

    /// Setup: record the root-update key and the genesis root (R^(0), e* = 0).
    function register(bytes calldata domain, address owner, bytes32 r0) external {
        require(msg.sender == admin, "only admin");
        require(domain.length > 0 && owner != address(0), "bad domain");
        bytes32 k = keccak256(domain);
        require(!domains[k].registered, "domain already registered");
        require(names.length < MAX_DOMAINS, "too many domains");
        domains[k] = Domain(owner, 0, r0, true);
        // insert keeping the names sorted, as Python's sorted() over the domain names
        names.push(domain);
        for (uint256 i = names.length - 1; i > 0 && _less(names[i], names[i - 1]); i--) {
            bytes memory tmp = names[i];
            names[i] = names[i - 1];
            names[i - 1] = tmp;
        }
        globalRoot = _globalRoot();
        emit Registered(domain, owner, r0, globalRoot);
    }

    /// Atomic transition (Phase 2, Step 5). Anyone may relay it; only the owner's signature counts.
    function submit(bytes calldata domain, uint64 epoch, bytes32 prev, bytes32 root, bytes32 delta,
                    bytes calldata sig) external {
        Domain storage d = domains[keccak256(domain)];
        require(d.registered, "unknown domain");
        require(prev == d.root, "predecessor root is not the current anchored root");
        require(epoch == d.epoch + 1, "epoch must be e* + 1");
        require(_signer(transitionDigest(domain, epoch, prev, root, delta), sig) == d.owner,
                "owner signature invalid");
        d.epoch = epoch;
        d.root = root;
        globalRoot = _globalRoot();
        emit Anchored(domain, epoch, prev, root, delta, globalRoot);
    }

    /// What a Data User reads: (e*, R*_D).
    function latest(bytes calldata domain) external view returns (uint64, bytes32) {
        Domain storage d = domains[keccak256(domain)];
        require(d.registered, "unknown domain");
        return (d.epoch, d.root);
    }

    function ownerOf(bytes calldata domain) external view returns (address) {
        return domains[keccak256(domain)].owner;
    }

    function domainCount() external view returns (uint256) {
        return names.length;
    }

    /// The 32-byte value the owner signs (before the EIP-191 prefix).
    function transitionDigest(bytes calldata domain, uint64 epoch, bytes32 prev, bytes32 root, bytes32 delta)
        public view returns (bytes32)
    {
        bytes memory m = abi.encodePacked(
            uint32(TAG_TRANSITION.length), TAG_TRANSITION,
            uint32(domain.length), domain,
            uint32(8), epoch,
            uint32(32), prev,
            uint32(32), root,
            uint32(32), delta);
        return sha256(abi.encodePacked(m, uint64(block.chainid), address(this)));
    }

    // ---------------------------------------------------------------- internals

    function _signer(bytes32 digest, bytes calldata sig) internal pure returns (address) {
        require(sig.length == 65, "signature must be 65 bytes");
        bytes32 r = bytes32(sig[0:32]);
        bytes32 s = bytes32(sig[32:64]);
        uint8 v = uint8(sig[64]);
        require(uint256(s) <= HALF_N, "malleable signature");
        require(v == 27 || v == 28, "bad v");
        bytes32 h = keccak256(abi.encodePacked("\x19Ethereum Signed Message:\n32", digest));
        address a = ecrecover(h, v, r, s);
        require(a != address(0), "bad signature");
        return a;
    }

    function _globalRoot() internal view returns (bytes32) {
        bytes32[] memory leaves = new bytes32[](names.length);
        for (uint256 i = 0; i < names.length; i++) {
            Domain storage d = domains[keccak256(names[i])];
            // H(i, e, R_D) as in anchor.py RootAnchor._global
            leaves[i] = sha256(abi.encodePacked(uint32(names[i].length), names[i],
                                                uint32(8), d.epoch, uint32(32), d.root));
        }
        return _merkleRoot(leaves);
    }

    function _merkleRoot(bytes32[] memory values) internal pure returns (bytes32) {
        uint256 size = 1;
        while (size < values.length) size *= 2;
        bytes32 pad = sha256(abi.encodePacked(uint32(1), bytes1(0x02)));
        bytes32[] memory level = new bytes32[](size);
        for (uint256 i = 0; i < size; i++) {
            level[i] = i < values.length
                ? sha256(abi.encodePacked(uint32(1), bytes1(0x00), uint32(32), values[i]))
                : pad;
        }
        while (size > 1) {
            size /= 2;
            for (uint256 i = 0; i < size; i++) {
                level[i] = sha256(abi.encodePacked(uint32(1), bytes1(0x01), uint32(32), level[2 * i],
                                                   uint32(32), level[2 * i + 1]));
            }
        }
        return level[0];
    }

    function _less(bytes memory a, bytes memory b) internal pure returns (bool) {
        uint256 n = a.length < b.length ? a.length : b.length;
        for (uint256 i = 0; i < n; i++) {
            if (a[i] != b[i]) return a[i] < b[i];
        }
        return a.length < b.length;
    }
}

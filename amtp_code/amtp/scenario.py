"""Demo world: two domains, four users, a dozen fictional records.

All names and records are invented for the demo. The real experiments use
the shared arXiv dataset-v4 (datasets/arxiv/) instead.
"""
from .adversary import Adversary
from .anchor import RootAnchor
from .core.crypto import make_authority
from .owner import DataOwner, DomainKeys
from .server import CloudServer
from .user import DataUser

DOMAINS = {
    "A": "City Hospital",
    "B": "Metabolic Research Lab",
}

DOCS = {
    "A": [
        ("A-01", "Diabetes follow-up", "Patient continues insulin therapy. Glucose stable, review diet plan.",
         "doctor AND hospital_a"),
        ("A-02", "Obesity clinic referral", "Referral to obesity clinic for weight management and exercise program.",
         "(doctor OR nurse) AND hospital_a"),
        ("A-03", "Insulin pump training", "Nurse training session on insulin pump setup and glucose monitoring.",
         "(doctor OR nurse) AND hospital_a"),
        ("A-04", "Hypertension review", "Blood pressure medication adjusted. Hypertension under control.",
         "doctor AND hospital_a"),
        ("A-05", "Ward staffing roster", "Night shift roster for nurse team, ward three.",
         "nurse AND hospital_a"),
        ("A-06", "Diabetes and obesity case", "Type two diabetes with obesity; start insulin, refer to dietitian.",
         "doctor OR researcher"),
        ("A-07", "Pharmacy stock report", "Insulin and metformin stock levels for the quarter.",
         "doctor AND hospital_a"),
    ],
    "B": [
        ("B-01", "Glucose sensor trial", "Clinical trial of continuous glucose sensor in diabetes patients.",
         "researcher AND lab_b"),
        ("B-02", "Obesity cohort study", "Cohort study linking obesity, sleep and insulin resistance.",
         "researcher OR doctor"),
        ("B-03", "Trial budget", "Budget for the insulin dosing trial, equipment and staff.",
         "auditor OR researcher"),
        ("B-04", "Ethics approval", "Ethics committee approval for the diabetes sensor trial.",
         "auditor OR researcher"),
        ("B-05", "Exercise and hypertension", "Pilot study of exercise effects on hypertension.",
         "researcher AND lab_b"),
    ],
}

# Documents the owner can publish later from the UI (each creates a new epoch).
PENDING = {
    "A": [
        ("A-08", "Insulin dose correction", "Urgent insulin dose correction after hypoglycemia event.",
         "doctor AND hospital_a"),
        ("A-09", "Obesity diet plan", "Low calorie diet plan for obesity patients, nurse led.",
         "(doctor OR nurse) AND hospital_a"),
        ("A-10", "Diabetes education class", "Group class on diabetes, glucose testing and insulin.",
         "doctor OR nurse OR researcher"),
    ],
    "B": [
        ("B-06", "Interim trial results", "Interim results: glucose sensor accuracy in diabetes trial.",
         "researcher AND lab_b"),
        ("B-07", "Audit of trial spending", "Audit of insulin trial spending and equipment.",
         "auditor"),
    ],
}

USERS = [
    # uid, name, role, attributes, domains with query keys
    ("mali", "Dr. Mali", "Doctor, City Hospital", ["doctor", "hospital_a"], ["A", "B"]),
    ("ton", "Ton", "Nurse, City Hospital", ["nurse", "hospital_a"], ["A"]),
    ("nina", "Nina", "Researcher, Research Lab", ["researcher", "lab_b"], ["A", "B"]),
    ("kit", "Kit", "External auditor", ["auditor"], ["B"]),
]

EXAMPLE_QUERIES = [
    "insulin",
    "diabetes AND insulin",
    "(diabetes AND insulin) OR obesity",
    "glucose OR hypertension",
    "trial AND (budget OR ethics)",
    "cancer",
]


def _doc(t):
    return {"id": t[0], "title": t[1], "body": t[2], "policy": t[3]}


class World:
    def __init__(self, theta_min=1, theta_max=4):
        self.authority = make_authority()
        self.anchor = RootAnchor()
        self.server = CloudServer()
        self.adversary = Adversary(self.server)     # demo and tests only
        self.keys = {d: DomainKeys() for d in DOMAINS}
        self.owners = {}
        self.pending = {d: [_doc(t) for t in PENDING[d]] for d in DOMAINS}
        for d in DOMAINS:
            self.server.register_query_key(d, self.keys[d].k_a)
            self.owners[d] = DataOwner(d, DOMAINS[d], self.keys[d], self.authority,
                                       self.anchor, self.server, theta_min, theta_max)
        self.users = {
            uid: DataUser(uid, name, role, attrs, self.authority.user_keys(attrs),
                          {d: self.keys[d] for d in domains})
            for uid, name, role, attrs, domains in USERS
        }
        for d in DOMAINS:
            docs = [_doc(t) for t in DOCS[d]]
            # Two epochs at start, so the 'old epoch' scenario has something to replay.
            self.owners[d].add_documents(docs[:-1])
            self.owners[d].add_documents(docs[-1:])

    def publish_next(self, domain):
        if not self.pending[domain]:
            return None
        doc = self.pending[domain].pop(0)
        self.owners[domain].add_documents([doc])
        return doc

    def plaintext_answer(self, domain, text):
        """Ground truth for tests only: run the Boolean query on plaintext keywords."""
        from .core import boolean
        from .index import extract_keywords
        published = [_doc(t) for t in DOCS[domain] + PENDING[domain]
                     if t[0] not in {p["id"] for p in self.pending[domain]}]
        from .nlp import norm
        sets = {}
        ast = boolean.parse(text)
        for w in boolean.leaves(ast):
            sets[w] = {d["id"] for d in published
                       if norm(w) in {norm(k) for k in extract_keywords(d["title"] + " " + d["body"])}}
        return boolean.evaluate(ast, sets)

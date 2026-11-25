"""Heuristic algorithms for EHR processing on synthetic data: record linkage and surgical-case scheduling.

Linkage pipeline: multi-pass phonetic blocking (Soundex) -> Jaro-Winkler field comparison -> weighted
score -> threshold -> union-find clusters. Scheduling: priority-rule heuristics (FIFO, EDD, WSPT) and
simulated annealing on the weighted tardiness of a list schedule over parallel operating rooms.

All records are synthetic. No real patient data is used or implied.
"""

from __future__ import annotations

import math
import random
from typing import Dict, List, Tuple

FIRST = ["Aiko", "Amir", "Ana", "Arjun", "Beatrice", "Carlos", "Chen", "Daniela", "David", "Elena", "Emma", "Farid",
         "Grace", "Hana", "Hiro", "Ibrahim", "Isabel", "Jin", "Julia", "Kenji", "Lakshmi", "Liam", "Maria", "Mei",
         "Mohammed", "Nadia", "Noah", "Olivia", "Priya", "Rahul", "Robert", "Sofia", "Sun", "Tariq", "Thomas",
         "Wei", "William", "Yuki", "Zainab", "Zhang"]
LAST = ["Abbott", "Ahmed", "Bailey", "Banerjee", "Campbell", "Chandra", "Chen", "Cohen", "Dubois", "Evans", "Fischer",
        "Garcia", "Gupta", "Hayashi", "Hughes", "Ibrahim", "Ivanov", "Jackson", "Kapoor", "Kim", "Lambert", "Li",
        "Martin", "Mehta", "Mitchell", "Nakamura", "Nguyen", "Okafor", "Patel", "Quinn", "Reddy", "Robinson",
        "Sato", "Singh", "Suzuki", "Tanaka", "Thompson", "Tran", "Wang", "Williams", "Wilson", "Yamamoto", "Zhao"]
NICK = {"Robert": "Bob", "William": "Bill", "Thomas": "Tom", "Elena": "Lena", "Daniela": "Dani", "Mohammed": "Mo"}


# ----------------------------------------------------------------------- string metrics

def soundex(name: str) -> str:
    """American Soundex (H and W do not separate equal codes)."""
    codes = {**dict.fromkeys("BFPV", "1"), **dict.fromkeys("CGJKQSXZ", "2"), **dict.fromkeys("DT", "3"),
             "L": "4", **dict.fromkeys("MN", "5"), "R": "6"}
    s = "".join(c for c in name.upper() if c.isalpha())
    if not s:
        return "0000"
    out = s[0]
    prev = codes.get(s[0], "")
    for c in s[1:]:
        code = codes.get(c, "")
        if code and code != prev:
            out += code
        if c not in "HW":
            prev = code
    return (out + "000")[:4]


def jaro(a: str, b: str) -> float:
    if a == b:
        return 1.0
    la, lb = len(a), len(b)
    if la == 0 or lb == 0:
        return 0.0
    window = max(la, lb) // 2 - 1
    ma, mb = [False] * la, [False] * lb
    matches = 0
    for i in range(la):
        for j in range(max(0, i - window), min(lb, i + window + 1)):
            if not mb[j] and a[i] == b[j]:
                ma[i] = mb[j] = True
                matches += 1
                break
    if matches == 0:
        return 0.0
    t, k = 0, 0
    for i in range(la):
        if ma[i]:
            while not mb[k]:
                k += 1
            if a[i] != b[k]:
                t += 1
            k += 1
    t //= 2
    return (matches / la + matches / lb + (matches - t) / matches) / 3.0


def jaro_winkler(a: str, b: str, p: float = 0.1) -> float:
    j = jaro(a, b)
    prefix = 0
    for x, y in zip(a[:4], b[:4]):
        if x != y:
            break
        prefix += 1
    return j + prefix * p * (1.0 - j)


# --------------------------------------------------------------------------- data

def generate_records(n_unique: int = 300, dup_rate: float = 0.2, seed: int = 1) -> List[Dict[str, object]]:
    if not (20 <= n_unique <= 2000) or not (0.0 <= dup_rate <= 0.6):
        raise ValueError("n_unique must be 20-2000 and dup_rate 0-0.6")
    rng = random.Random(seed)
    records: List[Dict[str, object]] = []
    for eid in range(n_unique):
        y, m, d = rng.randint(1940, 2005), rng.randint(1, 12), rng.randint(1, 28)
        records.append({"rid": len(records), "entity": eid, "first": rng.choice(FIRST), "last": rng.choice(LAST),
                        "dob": f"{y:04d}-{m:02d}-{d:02d}", "sex": rng.choice("MF"), "postal": f"{rng.randint(10000, 99999)}"})
    base = list(records)
    for src in rng.sample(base, int(round(dup_rate * n_unique))):
        rec = dict(src)
        rec["rid"] = len(records)
        for _ in range(rng.choice([1, 1, 2])):
            kind = rng.choice(["typo_first", "typo_last", "nick", "dob_swap", "dob_digit", "postal"])
            if kind in ("typo_first", "typo_last"):
                key = "first" if kind == "typo_first" else "last"
                v = rec[key]
                pos = rng.randrange(len(v) - 1)
                op = rng.choice(["swap", "drop", "sub"])
                if op == "swap":
                    v = v[:pos] + v[pos + 1] + v[pos] + v[pos + 2:]
                elif op == "drop":
                    v = v[:pos] + v[pos + 1:]
                else:
                    v = v[:pos] + rng.choice("aeiounrst") + v[pos + 1:]
                rec[key] = v
            elif kind == "nick" and rec["first"] in NICK:
                rec["first"] = NICK[rec["first"]]
            elif kind == "dob_swap":
                y, m, d = rec["dob"].split("-")
                if int(d) <= 12:
                    rec["dob"] = f"{y}-{d}-{m}"
            elif kind == "dob_digit":
                y, m, d = rec["dob"].split("-")
                rec["dob"] = f"{y}-{m}-{(int(d) % 28) + 1:02d}"
            elif kind == "postal":
                rec["postal"] = rec["postal"][:-1] + str((int(rec["postal"][-1]) + 1) % 10)
        records.append(rec)
    rng.shuffle(records)
    for i, r in enumerate(records):
        r["rid"] = i
    return records


WEIGHTS = {"first": 0.25, "last": 0.30, "dob": 0.30, "sex": 0.05, "postal": 0.10}


def pair_score(a: Dict[str, object], b: Dict[str, object]) -> float:
    dob = 1.0 if a["dob"] == b["dob"] else (0.6 if sum(x != y for x, y in zip(a["dob"], b["dob"])) <= 2 else 0.0)
    if dob < 1.0 and sorted(a["dob"].split("-")[1:]) == sorted(b["dob"].split("-")[1:]) and a["dob"][:4] == b["dob"][:4]:
        dob = max(dob, 0.8)
    postal = jaro_winkler(a["postal"], b["postal"])
    return (WEIGHTS["first"] * jaro_winkler(a["first"].lower(), b["first"].lower()) +
            WEIGHTS["last"] * jaro_winkler(a["last"].lower(), b["last"].lower()) +
            WEIGHTS["dob"] * dob + WEIGHTS["sex"] * (1.0 if a["sex"] == b["sex"] else 0.0) + WEIGHTS["postal"] * postal)


def blocking_keys(r: Dict[str, object]) -> List[str]:
    return ["A:" + soundex(r["last"]) + r["dob"][:4], "B:" + soundex(r["first"]) + r["dob"][5:], "C:" + soundex(r["last"]) + r["postal"][:3]]


def candidate_pairs(records: List[Dict[str, object]]) -> List[Tuple[int, int]]:
    blocks: Dict[str, List[int]] = {}
    for r in records:
        for k in blocking_keys(r):
            blocks.setdefault(k, []).append(r["rid"])
    pairs = set()
    for ids in blocks.values():
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                pairs.add((ids[i], ids[j]))
    return sorted(pairs)


class UnionFind:
    def __init__(self, n: int):
        self.p = list(range(n))

    def find(self, x: int) -> int:
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra


def link_records(records: List[Dict[str, object]], threshold: float = 0.86) -> Dict[str, object]:
    n = len(records)
    total_pairs = n * (n - 1) // 2
    cands = candidate_pairs(records)
    scored = [(i, j, pair_score(records[i], records[j])) for i, j in cands]
    truth: Dict[int, List[int]] = {}
    for r in records:
        truth.setdefault(r["entity"], []).append(r["rid"])
    true_pairs = {(a, b) for ids in truth.values() for x, a in enumerate(sorted(ids)) for b in sorted(ids)[x + 1:]}

    def metrics(th: float) -> Dict[str, float]:
        linked = {(i, j) for i, j, s in scored if s >= th}
        tp, fp = len(linked & true_pairs), len(linked - true_pairs)
        fn = len(true_pairs - linked)
        prec = tp / (tp + fp) if tp + fp else 1.0
        rec = tp / (tp + fn) if tp + fn else 1.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        return {"threshold": th, "precision": prec, "recall": rec, "f1": f1, "tp": tp, "fp": fp, "fn": fn}

    curve = [metrics(round(t, 3)) for t in [0.6 + 0.02 * i for i in range(20)]]
    m = metrics(threshold)
    uf = UnionFind(n)
    edges = []
    linked = {(i, j) for i, j, s in scored if s >= threshold}
    for i, j in linked:
        uf.union(i, j)
        edges.append({"a": i, "b": j, "kind": "tp" if (i, j) in true_pairs else "fp"})
    for i, j in sorted(true_pairs - linked):
        edges.append({"a": i, "b": j, "kind": "fn"})
    clusters: Dict[int, List[int]] = {}
    for r in records:
        clusters.setdefault(uf.find(r["rid"]), []).append(r["rid"])
    return {"n_records": n, "total_pairs": total_pairs, "candidate_pairs": len(cands),
            "reduction_ratio": 1.0 - len(cands) / total_pairs, "metrics": m, "curve": curve,
            "clusters": sum(1 for c in clusters.values() if len(c) > 1), "entities": len(truth),
            "predicted_entities": len(clusters), "edges": edges, "records": records,
            "assignment": {r["rid"]: uf.find(r["rid"]) for r in records}}


# -------------------------------------------------------------------------- scheduling

def generate_cases(n: int = 24, seed: int = 3) -> List[Dict[str, float]]:
    rng = random.Random(seed)
    return [{"id": i, "duration": rng.choice([45, 60, 90, 120, 150, 180, 240]), "weight": rng.choice([1, 1, 2, 3, 5]),
             "due": rng.randint(120, 720)} for i in range(n)]


def decode(order: List[int], cases: List[Dict[str, float]], rooms: int) -> Tuple[float, List[Dict[str, float]]]:
    free = [0.0] * rooms
    total = 0.0
    segs = []
    for idx in order:
        c = cases[idx]
        r = min(range(rooms), key=lambda x: free[x])
        start = free[r]
        end = start + c["duration"]
        free[r] = end
        total += c["weight"] * max(0.0, end - c["due"])
        segs.append({"id": c["id"], "room": r, "start": start, "end": end, "weight": c["weight"], "due": c["due"]})
    return total, segs


def schedule(cases: List[Dict[str, float]], rooms: int = 3, seed: int = 5, steps: int = 4000) -> Dict[str, object]:
    n = len(cases)
    rules = {
        "FIFO": list(range(n)),
        "EDD": sorted(range(n), key=lambda i: cases[i]["due"]),
        "WSPT": sorted(range(n), key=lambda i: -cases[i]["weight"] / cases[i]["duration"]),
    }
    results = {k: decode(v, cases, rooms)[0] for k, v in rules.items()}
    best_rule = min(results, key=results.get)
    rng = random.Random(seed)
    cur = list(rules[best_rule])
    cur_c = results[best_rule]
    best, best_c = list(cur), cur_c
    trace = [best_c]
    for s in range(steps):
        temp = max(1e-3, 0.3 * cur_c * (1 - s / steps))
        i, j = rng.sample(range(n), 2)
        cand = list(cur)
        if rng.random() < 0.5:
            cand[i], cand[j] = cand[j], cand[i]
        else:
            cand.insert(j, cand.pop(i))
        c = decode(cand, cases, rooms)[0]
        if c < cur_c or rng.random() < math.exp(-(c - cur_c) / temp):
            cur, cur_c = cand, c
        if cur_c < best_c:
            best, best_c = list(cur), cur_c
        if s % 200 == 0:
            trace.append(best_c)
    _, segs = decode(best, cases, rooms)
    return {"rules": results, "best_rule": best_rule, "annealing": best_c, "improvement_vs_best_rule": 1.0 - best_c / results[best_rule] if results[best_rule] else 0.0,
            "trace": trace, "segments": segs, "rooms": rooms, "cases": cases}

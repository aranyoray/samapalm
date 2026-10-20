"""Schema-driven CRF engine shared with the Android onboarding app (configs/crf_schema.json).

The Kotlin engine in android/crf-core implements the same semantics; configs/crf_fixtures/*.json are golden cases
that both engines must reproduce exactly (tests/test_core_crf_schema.py and the Kotlin CrfEngineGoldenTest).

Semantics (keep in step with android/crf-core/src/main/kotlin/org/samahealth/crf/CrfEngine.kt):

* Flow: `flows[settings.clip_plan]` gives the screen order. A screen is visible when its `show_if` holds.
* Effective answers: one forward pass over visible screens and their questions in order; a question is visible when
  its `show_if` holds on the effective answers collected so far. Answers to hidden questions are dropped, so a changed
  branch never leaks stale answers into the export. Conditions may only refer to earlier questions (schema lint).
* Conditions: {"all": [...]}, {"any": [...]}, {"not": c}, or a leaf {"q"|"setting"|"derived": key, [field], op}.
  Ops: eq, ne, in, not_in, lt, lte, gt, gte, between [lo, hi] inclusive, contains (list membership), answered.
  Numeric ops are false for non-numbers; `ne` is true when the value is missing.
* Validation codes: required, type, min, max, choice, exclusive, pattern, date, future, bp_range, bp_order, bp_time,
  clip_incomplete, clip_order, stop. Warnings (non-blocking) come from `warn_if`.
* Derived values: bmi, cuff_suggestion, trimester, rest_elapsed_s, recovery, bracket_flag, bp1_outlier, eligible,
  initials (see `derive`).
* Export: answered effective questions with store "crf" (default) and `export` not false, transformed by
  `export_as`; computed questions marked `export: true`; plus context and `initials`. Identity questions go to a
  separate record keyed by PID (name and PID are stored apart).
"""
from __future__ import annotations

import datetime as dt
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "configs" / "crf_schema.json"
NO_VALUE_TYPES = {"computed", "info"}
BP_LIMITS = {"sbp": (50, 300), "dbp": (20, 200), "hr": (20, 250)}


def load_schema(path: str | Path | None = None) -> dict:
    return json.loads(Path(path or SCHEMA_PATH).read_text(encoding="utf-8"))


def answered(v: Any) -> bool:
    if v is None:
        return False
    if isinstance(v, str):
        return v.strip() != ""
    if isinstance(v, (list, tuple, dict)):
        return len(v) > 0
    return True


def _is_num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and not (isinstance(v, float) and math.isnan(v))


def parse_ts(s: Any) -> dt.datetime | None:
    """ISO 8601 timestamp with offset (naive values are read as UTC)."""
    if not isinstance(s, str) or not s:
        return None
    try:
        t = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def parse_date(s: Any) -> dt.date | None:
    if not isinstance(s, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return None
    try:
        return dt.date.fromisoformat(s)
    except ValueError:
        return None


def eval_condition(cond: Mapping | None, answers: Mapping, settings: Mapping, derived: Mapping | None = None) -> bool:
    if cond is None:
        return True
    if "all" in cond:
        return all(eval_condition(c, answers, settings, derived) for c in cond["all"])
    if "any" in cond:
        return any(eval_condition(c, answers, settings, derived) for c in cond["any"])
    if "not" in cond:
        return not eval_condition(cond["not"], answers, settings, derived)
    if "q" in cond:
        v = answers.get(cond["q"])
    elif "setting" in cond:
        v = settings.get(cond["setting"])
    elif "derived" in cond:
        v = (derived or {}).get(cond["derived"])
    else:
        raise ValueError(f"condition without a subject: {cond}")
    if "field" in cond:
        v = v.get(cond["field"]) if isinstance(v, Mapping) else None
    if "eq" in cond:
        return answered(v) and v == cond["eq"] if not isinstance(cond["eq"], bool) else v is cond["eq"]
    if "ne" in cond:
        return v != cond["ne"]
    if "in" in cond:
        return answered(v) and v in cond["in"]
    if "not_in" in cond:
        return answered(v) and v not in cond["not_in"]
    if "contains" in cond:
        return isinstance(v, (list, tuple)) and cond["contains"] in v
    if "answered" in cond:
        return answered(v) == bool(cond["answered"])
    for op, fn in (("lt", lambda a, b: a < b), ("lte", lambda a, b: a <= b), ("gt", lambda a, b: a > b), ("gte", lambda a, b: a >= b)):
        if op in cond:
            return _is_num(v) and fn(v, cond[op])
    if "between" in cond:
        lo, hi = cond["between"]
        return _is_num(v) and lo <= v <= hi
    raise ValueError(f"unknown condition operator: {cond}")


def resolve_default(q: Mapping, settings: Mapping) -> Any:
    d = q.get("default")
    if isinstance(d, str) and d.startswith("$settings."):
        return settings.get(d[len("$settings."):])
    return d


@dataclass
class Issue:
    q: str
    code: str
    message: str
    screen: str

    def key(self) -> str:
        return f"{self.q}:{self.code}"


@dataclass
class Evaluation:
    visible_screens: list[str]
    visible_questions: dict[str, list[str]]
    effective: dict[str, Any]
    derived: dict[str, Any]
    errors: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)
    stopped: Issue | None = None


class CrfEngine:
    def __init__(self, schema: Mapping | None = None, settings: Mapping | None = None):
        self.schema = dict(schema or load_schema())
        self.settings = {**self.schema.get("settings_defaults", {}), **dict(settings or {})}
        self.screens = {s["id"]: s for s in self.schema["screens"]}
        self.questions: dict[str, tuple[dict, dict]] = {}
        for s in self.schema["screens"]:
            for q in s["questions"]:
                if q["id"] in self.questions:
                    raise ValueError(f"duplicate question id {q['id']}")
                self.questions[q["id"]] = (s, q)
        self.pid_re = re.compile(self.schema["pid_pattern"])

    # ------------------------------------------------------------------ helpers
    def flow(self) -> list[str]:
        plan = self.settings.get("clip_plan")
        if plan not in self.schema["flows"]:
            raise ValueError(f"unknown clip_plan {plan!r}; schema flows: {sorted(self.schema['flows'])}")
        return list(self.schema["flows"][plan])

    def choice_values(self, q: Mapping) -> list[str]:
        ch = q.get("choices")
        lst = self.schema["choices"][ch] if isinstance(ch, str) else (ch or [])
        return [c["value"] for c in lst]

    def initial_answers(self) -> dict[str, Any]:
        """Defaults for questions that declare one (the app pre-fills these)."""
        out = {}
        for _, q in self.questions.values():
            d = resolve_default(q, self.settings)
            if d is not None:
                out[q["id"]] = d
        return out

    # ------------------------------------------------------------------ evaluation
    def evaluate(self, answers: Mapping, now: dt.datetime | None = None) -> Evaluation:
        now = now or dt.datetime.now(dt.timezone.utc)
        effective: dict[str, Any] = {}
        vis_screens, vis_q = [], {}
        for sid in self.flow():
            s = self.screens[sid]
            if not eval_condition(s.get("show_if"), effective, self.settings, derive(effective, self.settings, now)):
                continue
            vis_screens.append(sid)
            vis_q[sid] = []
            for q in s["questions"]:
                if not eval_condition(q.get("show_if"), effective, self.settings, derive(effective, self.settings, now)):
                    continue
                vis_q[sid].append(q["id"])
                if q["type"] not in NO_VALUE_TYPES and answered(answers.get(q["id"])):
                    effective[q["id"]] = answers[q["id"]]
        der = derive(effective, self.settings, now)
        ev = Evaluation(vis_screens, vis_q, effective, der)
        for sid in vis_screens:
            for qid in vis_q[sid]:
                q = self.questions[qid][1]
                for code, msg in self._check(q, effective, der, now):
                    ev.errors.append(Issue(qid, code, msg, sid))
                if q.get("stop_if") and eval_condition(q["stop_if"], effective, self.settings, der):
                    iss = Issue(qid, "stop", q.get("stop_message", "stop"), sid)
                    ev.errors.append(iss)
                    if ev.stopped is None:
                        ev.stopped = iss
                if q.get("warn_if") and eval_condition(q["warn_if"], effective, self.settings, der):
                    ev.warnings.append(Issue(qid, "warn", q.get("warn_message", ""), sid))
        return ev

    def _check(self, q: Mapping, eff: Mapping, der: Mapping, now: dt.datetime) -> list[tuple[str, str]]:
        t, qid = q["type"], q["id"]
        if t in NO_VALUE_TYPES:
            return []
        v = eff.get(qid)
        req = bool(q.get("required")) or (q.get("required_if") is not None and eval_condition(q["required_if"], eff, self.settings, der))
        if not answered(v):
            return [("required", "required")] if req else []
        out: list[tuple[str, str]] = []
        if t in ("integer", "mst"):
            if not (isinstance(v, int) and not isinstance(v, bool)):
                return [("type", "whole number expected")]
        if t == "decimal" and not _is_num(v):
            return [("type", "number expected")]
        if t in ("integer", "decimal", "mst"):
            if "min" in q and v < q["min"]:
                out.append(("min", f"minimum {q['min']}"))
            if "max" in q and v > q["max"]:
                out.append(("max", f"maximum {q['max']}"))
        elif t == "single":
            if v not in self.choice_values(q):
                out.append(("choice", "not one of the listed options"))
        elif t == "multi":
            if not isinstance(v, list) or any(x not in self.choice_values(q) for x in v):
                out.append(("choice", "not one of the listed options"))
            elif any(x in v for x in q.get("exclusive", [])) and len(v) > 1:
                out.append(("exclusive", "this option cannot be combined with others"))
        elif t == "pid":
            if not isinstance(v, str) or not self.pid_re.match(v):
                out.append(("pattern", "PID format SWHT-PP-003-####"))
        elif t == "text":
            if q.get("pattern") and not re.fullmatch(q["pattern"], str(v)):
                out.append(("pattern", "format not recognised"))
        elif t == "date":
            d = parse_date(v)
            if d is None:
                out.append(("date", "date as YYYY-MM-DD"))
            elif d > now.date():
                out.append(("future", "date is in the future"))
        elif t == "bp":
            out += self._check_bp(v)
        elif t == "clip":
            out += self._check_clip(v)
        return out

    @staticmethod
    def _check_bp(v: Any) -> list[tuple[str, str]]:
        if not isinstance(v, Mapping):
            return [("type", "reading expected")]
        for k, (lo, hi) in BP_LIMITS.items():
            x = v.get(k)
            if not (isinstance(x, int) and not isinstance(x, bool)) or not lo <= x <= hi:
                return [("bp_range", f"{k} must be a whole number in {lo}-{hi}")]
        if v["sbp"] <= v["dbp"]:
            return [("bp_order", "SBP must exceed DBP")]
        if parse_ts(v.get("wall_ts")) is None:
            return [("bp_time", "reading time missing")]
        return []

    @staticmethod
    def _check_clip(v: Any) -> list[tuple[str, str]]:
        if not isinstance(v, Mapping):
            return [("type", "clip record expected")]
        a, b = parse_ts(v.get("started_at")), parse_ts(v.get("ended_at"))
        if a is None or b is None or v.get("quality") not in ("pass", "fail"):
            return [("clip_incomplete", "start, end and quality are needed")]
        if b <= a:
            return [("clip_order", "end must be after start")]
        return []

    # ------------------------------------------------------------------ export
    def export(self, answers: Mapping, context: Mapping | None = None, identity_name: str | None = None,
               now: dt.datetime | None = None) -> tuple[dict, dict]:
        """(crf record, identity record). The CRF never contains identity-store answers."""
        ev = self.evaluate(answers, now)
        crf: dict[str, Any] = {}
        ident: dict[str, Any] = {}
        for sid in ev.visible_screens:
            for qid in ev.visible_questions[sid]:
                q = self.questions[qid][1]
                if q["type"] == "computed":
                    if q.get("export") and ev.derived.get(q.get("compute", qid)) is not None:
                        crf[q.get("export_key", qid)] = ev.derived[q.get("compute", qid)]
                    continue
                if q["type"] == "info" or qid not in ev.effective:
                    continue
                v = ev.effective[qid]
                if q.get("store") == "identity":
                    ident[qid] = v
                    continue
                if q.get("export") is False:
                    continue
                if q.get("export_as") == "bool_yes_no":
                    v = {"yes": True, "no": False}.get(v)
                crf[q.get("export_key", qid)] = v
        name = identity_name if identity_name is not None else ident.get("name")
        if name:
            crf["initials"] = initials(name)
        ident["pid"] = ev.effective.get("study_id")
        crf.update({k: v for k, v in dict(context or {}).items() if v is not None})
        crf["schema_version"] = self.schema["schema_version"]
        crf["clip_plan"] = self.settings.get("clip_plan")
        return crf, ident


# ---------------------------------------------------------------------- derivations
def initials(name: str) -> str:
    parts = [p for p in re.split(r"\s+", name.strip()) if p]
    return "".join(p[0].upper() for p in parts[:3])


def cuff_suggestion(circ: Any) -> str | None:
    if not _is_num(circ):
        return None
    if circ < 17:
        return "below small adult range"
    if circ < 22:
        return "small adult"
    if circ < 32:
        return "adult"
    if circ < 42:
        return "large adult"
    if circ <= 52:
        return "thigh"
    return "above thigh range"


def derive(eff: Mapping, settings: Mapping, now: dt.datetime | None = None) -> dict[str, Any]:
    """Display and export derivations from the effective answers (protocol 3.1 derived fields the operator sees)."""
    now = now or dt.datetime.now(dt.timezone.utc)
    out: dict[str, Any] = {}
    h, w = eff.get("height_cm"), eff.get("weight_kg")
    out["bmi"] = round(w / (h / 100.0) ** 2, 1) if _is_num(h) and _is_num(w) and h > 0 else None
    out["cuff_suggestion"] = cuff_suggestion(eff.get("arm_circumference_cm"))
    ga = eff.get("gestational_age_weeks")
    out["trimester"] = (1 if ga < 14 else 2 if ga < 28 else 3) if _is_num(ga) else None
    bp = {k: eff.get(k) for k in ("bp1", "bp2", "bp3")}
    t1 = parse_ts(bp["bp1"].get("wall_ts")) if isinstance(bp["bp1"], Mapping) else None
    t2 = parse_ts(bp["bp2"].get("wall_ts")) if isinstance(bp["bp2"], Mapping) else None
    out["rest_elapsed_s"] = int(((t2 or now) - t1).total_seconds()) if t1 else None
    c1 = eff.get("clip1")
    tc = parse_ts(c1.get("started_at")) if isinstance(c1, Mapping) else None
    if t1 and tc:
        out["recovery"] = "pass" if (tc - t1).total_seconds() >= float(settings.get("rest_seconds", 300)) else "short_rest"
    else:
        out["recovery"] = None
    readings = [r for r in bp.values() if isinstance(r, Mapping) and _is_num(r.get("sbp")) and _is_num(r.get("dbp"))]
    if len(readings) >= 2:
        lim = float(settings.get("bracket_mmhg", 10))
        out["bracket_flag"] = any(max(r[k] for r in readings) - min(r[k] for r in readings) > lim for k in ("sbp", "dbp"))
    else:
        out["bracket_flag"] = None
    b1 = bp["bp1"] if isinstance(bp["bp1"], Mapping) else None
    later = [r for r in (bp["bp2"], bp["bp3"]) if isinstance(r, Mapping) and _is_num(r.get("sbp")) and _is_num(r.get("dbp"))]
    if b1 and _is_num(b1.get("sbp")) and _is_num(b1.get("dbp")) and later:
        lim = float(settings.get("bp1_outlier_mmhg", 15))
        out["bp1_outlier"] = any(abs(b1[k] - sum(r[k] for r in later) / len(later)) > lim for k in ("sbp", "dbp"))
    else:
        out["bp1_outlier"] = None
    age, consent = eff.get("age"), eff.get("consent")
    out["eligible"] = (consent == "yes" and age >= 18) if (consent is not None and _is_num(age)) else None
    out["rest_elapsed"] = out["rest_elapsed_s"]
    return out


def lint_schema(schema: Mapping) -> list[str]:
    """Static checks: unique ids, known choice lists, flows reference known screens, conditions refer to earlier
    questions in every flow (so one forward pass is enough), computed questions name a known derivation."""
    problems = []
    known_derived = {"bmi", "cuff_suggestion", "trimester", "rest_elapsed", "rest_elapsed_s", "recovery", "bracket_flag", "bp1_outlier", "eligible"}
    screens = {s["id"]: s for s in schema["screens"]}
    seen = set()
    for s in schema["screens"]:
        for q in s["questions"]:
            if q["id"] in seen:
                problems.append(f"duplicate question {q['id']}")
            seen.add(q["id"])
            if isinstance(q.get("choices"), str) and q["choices"] not in schema["choices"]:
                problems.append(f"{q['id']}: unknown choice list {q['choices']}")
            if q["type"] == "computed" and q.get("compute") not in known_derived:
                problems.append(f"{q['id']}: unknown derivation {q.get('compute')}")

    def refs(c):
        if not c:
            return []
        if "all" in c or "any" in c:
            return [r for x in c.get("all", c.get("any", [])) for r in refs(x)]
        if "not" in c:
            return refs(c["not"])
        return [c["q"]] if "q" in c else []

    for plan, order in schema["flows"].items():
        before: set[str] = set()
        for sid in order:
            if sid not in screens:
                problems.append(f"flow {plan}: unknown screen {sid}")
                continue
            s = screens[sid]
            for r in refs(s.get("show_if")):
                if r not in before:
                    problems.append(f"flow {plan}: screen {sid} show_if refers to {r}, not asked earlier")
            for q in s["questions"]:
                for key in ("show_if", "required_if"):
                    for r in refs(q.get(key)):
                        if r not in before and not (key == "required_if" and r in {x["id"] for x in s["questions"]}):
                            problems.append(f"flow {plan}: {q['id']} {key} refers to {r}, not asked earlier")
                before.add(q["id"])
    return problems

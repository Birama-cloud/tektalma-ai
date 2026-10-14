"""Évaluation rapide. Lancer :  python -m scripts.eval_rag"""
import json
import time

from app.pipeline import Tektalma
from config import settings

if __name__ == "__main__":
    engine = Tektalma()
    rows = [json.loads(line) for line in
            (settings.BASE_DIR / "tests" / "eval_set.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()]
    kind_ok, hits, rr, n_retr = 0, 0, 0.0, 0
    good_sims, bad_sims = [], []
    for r in rows:
        ans = engine.ask(r["question"])
        retrieved = ans.debug.get("retrieved", [])
        names = [f for f, _ in retrieved]
        ok_kind = ans.kind == r["attendu"]
        kind_ok += ok_kind
        mark = "✅" if ok_kind else "❌"
        if r["fiches"]:
            n_retr += 1
            rank = next((i + 1 for i, f in enumerate(names) if f in r["fiches"]), None)
            if rank:
                hits += 1
                rr += 1 / rank
            if retrieved:
                (good_sims if rank else bad_sims).append(max(sim for _, sim in retrieved))
        elif retrieved:
            bad_sims.append(max(sim for _, sim in retrieved))
        u = ans.debug.get("understanding", {})
        print(f"{mark} [{r['langue']}] {r['question']}\n"
              f"     type={ans.kind} (attendu {r['attendu']}) · langue détectée={u.get('language')}\n"
              f"     reformulée : {u.get('standalone_question_fr')}\n"
              f"     fiches : {retrieved}")
        if ans.debug.get("removed_sentences"):
            print(f"     ⚠️ phrases retirées (chiffres non sourcés) : {ans.debug['removed_sentences']}")
        time.sleep(2)  # ménage le quota gratuit
    print(f"\nType de réponse correct : {kind_ok}/{len(rows)}")
    if n_retr:
        print(f"Hit@{settings.TOP_DOCS} : {hits}/{n_retr} · MRR : {rr / n_retr:.2f}")
    if good_sims:
        print(f"Similarité des bonnes fiches : min {min(good_sims):.3f}")
    if bad_sims:
        print(f"Similarité des cas sans bonne fiche : max {max(bad_sims):.3f}")
    print(f"Seuil actuel MIN_SIMILARITY = {settings.MIN_SIMILARITY} "
          "(à placer entre ces deux valeurs, dans .env)")
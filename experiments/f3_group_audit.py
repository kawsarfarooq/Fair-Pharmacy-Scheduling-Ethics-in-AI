from trustworthy_common import *


def main():
    args = options("Synthetic group audit with paired availability-proxy ablation")
    rows = []
    for seed in range(args.seeds):
        for proxy in (True, False):
            inst = audit_scenario(seed)
            if not proxy:
                # Paired ablation removes only the deliberately injected proxy.
                raw = __import__("fair_scheduling.model", fromlist=["generate_instance"]).generate_instance(2, 8, 2, 7, seed)
                for w in inst.workers:
                    w.unavailable = set(raw.workers[w.wid].unavailable)
            for definition in ("utilitarian", "variance", "egalitarian", "lexicographic"):
                _, row = measured(inst, args, fairness=definition)
                rows.append({"seed": seed, "proxy": proxy, "method": definition, **row})
    save(rows, args, "f3_group_audit", ["proxy", "method"], "carer_undesirable_gap")


if __name__ == "__main__":
    main()

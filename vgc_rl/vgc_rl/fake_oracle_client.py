from __future__ import annotations

from typing import Any


class FakeOracleClient:
    def batch(self, body: dict[str, Any]) -> dict[str, Any]:
        results: list[dict[str, Any]] = []

        for req in body["requests"]:
            k = req["kind"]

            if k == "speedCompare":
                left = req["attacker"]
                pos = int(left.get("activeMovePosition") or 1)
                mv = str(left["moves"][pos - 1]["name"])

                results.append({"ok": True, "result": {"firstSpecies": left["name"], "firstMove": mv}})
            elif k == "single":
                results.append(
                    {
                        "ok": True,
                        "result": {
                            "moveName": "Tackle",
                            "damagePercentMin": 12.0,
                            "damagePercentMax": 12.0,
                            "koChanceText": "",
                        },
                    }
                )
            else:
                results.append({"ok": False, "error": f"unexpected kind {k}"})

        return {"results": results}

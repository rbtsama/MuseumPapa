"""Map benefit_id -> BPL LibCal pass-id.

BPL passes live at https://bpl.libcal.com/passes/<pass_id>. Hand-curated from
the public listing at https://bpl.libcal.com/passes; re-run that listing in a
browser if BPL adds/removes passes.

Hale Education (physical pass) at BPL has no matching benefit in this project's
data — skipped intentionally.
"""

BPL_PASS_ID = {
    "american-rep-theater":       "5bf37dc2bee6",
    "boch-center":                "572fd99e65a3",
    "boston-childrens-museum":    "247124590599",
    "boston-harbor-islands":      "a6c8020ee3e0",
    "greenway-carousel":          "85ce3124733e",
    "harvard-museums":            "92c222667367",
    "ica-boston":                 "ca412b08c3fc",
    "isabella-stewart-gardner":   "3f1a0abfb37f",
    "larz-anderson":              "c4d127379588",
    "ma-state-parks":             "96efc267af24",
    "mapparium":                  "ee42fe43a508",
    "mass-audubon":               "76269f5073ed",
    "mfa":                        "ced5467b5fe7",
    "museum-of-science":          "25815fed11ec",
    "new-england-aquarium":       "5478304b3d42",
    "paddle-boston":              "7dfc5eb56d0b",
    "peabody-essex-museum":       "cb71fd360f1d",
    "revolutionary-spaces":       "a86b0e178ad8",
    "sandwich-glass":             "c3c3953a4d27",
    "trustees-of-reservations":   "eb6d133c0fb7",
    "uss-constitution-museum":    "f3fe5e025455",
    "zoo-new-england":            "b91f556dbfb2",
}

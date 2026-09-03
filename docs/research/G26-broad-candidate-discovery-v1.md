# G26 broad candidate discovery

G26 extends Sunset's deterministic observation surface without claiming that
any signal is obsolete. The collector reads only committed Git HEAD paths and
emits provenance-bound leads for four bounded families:

- `support_constraint` in Python/package/repository configuration;
- `deprecation_lifecycle` in Python, JavaScript, and TypeScript;
- `feature_flag` references; and
- `environment_gate` references.

Dynamic flag and environment lookups remain candidates with
`unsupported_dynamic=true`; they are not converted into expiry conclusions.
The fixture demonstrates Python and TypeScript extraction, exact Git blame,
stable IDs, and exclusion of an untracked file.

G26 broadens candidate observability, not epistemic authority. G25's selected
configuration and G27's pilot must use only the signal families and language
scopes whose fixture coverage and unsupported forms are documented.

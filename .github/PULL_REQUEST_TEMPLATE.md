## Summary

- describe the change
- describe why it is needed

## Verification

- [ ] `python -m unittest discover -s tests`
- [ ] `python -m compileall app`
- [ ] `node --check cloudflare/worker.js`

## Risk Review

- [ ] no credentials, cookies, tokens, or webhook URLs were committed
- [ ] README or docs were updated if workflows, APIs, or secrets changed
- [ ] storage or event format changes were reviewed for backward compatibility

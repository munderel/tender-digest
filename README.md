# tender-digest

A daily email of new **federal IT and cloud tenders**, taken from the CanadaBuys open-data
file. It runs on a GitHub Actions cron at 09:45 Eastern and needs nothing but the Python
standard library.

## What the email holds

| Section | What is in it |
| --- | --- |
| Bid now | Open competitions and advance contract award notices a supplier can answer today |
| Supplier lists you could join | Requests for supply arrangement and invitations to qualify |
| Requests for information | Market research you can answer to get known by a buyer |
| Teaming leads | Work only existing list holders or invited suppliers can bid on |
| Closing within 5 days | Notices from earlier digests you could still act on |
| Supplier-list watch | The current amendment of ProServices, TBIPS, SBIPS, the SaaS Supply Arrangement, the AI Source List and the Software Licensing Supply Arrangement, plus any change since yesterday |

The first run lists everything IT or cloud that is open. After that, only new notices and
new amendments. **The email is sent every day, even when nothing is new.** A day without it
means the job broke.

## What it does not cover

The CanadaBuys file holds **federal notices only** ([dataset](https://open.canada.ca/data/en/dataset/6abd20d4-7a1c-4b38-baa2-9525d0bb2fd2),
Open Government Licence - Canada). Provincial, municipal and broader-public-sector tenders are
not in it. MERX, Biddingo and bids&tenders forbid automated collection in their terms, so this
job never scrapes them. Use their own email alerts, and the Ontario Tenders Portal's.

## Setup

1. Turn on 2-Step Verification for the sending Gmail account, then create an app password at
   <https://myaccount.google.com/apppasswords>.
2. Set three repository secrets, one command at a time. Each prompts for the value, so it never
   lands in shell history:

   ```
   gh secret set GMAIL_USER --repo munderel/tender-digest
   gh secret set GMAIL_APP_PASSWORD --repo munderel/tender-digest
   gh secret set DIGEST_TO --repo munderel/tender-digest
   ```

   `DIGEST_TO` takes one address, or several separated by commas.
3. Run it once by hand: `gh workflow run daily.yml --repo munderel/tender-digest`. That sends the
   first-run email and commits the first `state/seen.json`. A workflow that has never run looks
   exactly like a healthy one, so do not skip this.

## Run it locally

```
python -m tender_digest.run --dry-run
python -m pytest -q
```

`--dry-run` prints the digest and writes `out/digest.html`; it sends nothing and saves no state.
`--csv FILE` reads a saved copy of the file instead of downloading it.

## Tuning

Edit [`profile.toml`](profile.toml), not the code:

- `codes.prefixes`: UNSPSC prefixes that count as IT or cloud work.
- `keywords.anywhere`, `title_only`, `exact_words`: words that count, for services notices.
- `keywords.exclude`: words that drop a keyword-only match.
- `sections`: which notice types and methods land in which section.
- `vehicles`: the supplier lists to watch.

## When it breaks

- A failed run emails the last 2,500 characters of its log with the run link.
- If Gmail is what broke, that alert fails too. The missing daily email is then the signal, and
  GitHub emails the repository owner about the failed run.
- If CanadaBuys renames a column or serves a short file, the run fails on purpose rather than
  sending a "nothing new" email.

## Why the repository is public

GitHub Actions minutes are free and unlimited for public repositories. Private repositories on
this account share a monthly allowance that has run out before. Nothing here is secret: the
credentials live in repository secrets, and `state/seen.json` holds only public notice numbers.

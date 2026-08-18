# VOICE.md

The voice authority for Mazdoor outreach is the user's supplied outreach sample, not casual chat messages. Do not imitate misspellings or lowercase abbreviations from chat history.

## Sample (authoritative)

```
Hey Name,

I'm Hadi. Product Engineer.

[Specific company/job hook.]

I also run Parhlai. 8,281 users. PKR 500,079 booked revenue.

[One concrete family evidence line.]

Hope to talk to you :)
```

Short, blunt, human. Casual hook, quantified proof, no em dashes, no filler, no corporate language.

## Rules

1. **Open with a direct, specific hook** referencing the job/company, then use verified metrics instead of adjectives.
2. **No em dashes** (use plain hyphens). Also no en dashes.
3. **No filler or corporate language.** Banned: "I am writing to express", "I hope this finds you well", "I look forward to hearing from you", "I would love the opportunity", "Please find attached", "passionate about", "excited to potentially", "leverage", "Additionally", "Moreover", "I believe that".
4. **No AI tells** (per the humanizer skill): no rule-of-three lists, no -ing fake depth ("highlighting...", "ensuring..."), no reassurance kickers ("And that's okay"), no rhetorical questions answered immediately.
5. **No chat typos or lowercase abbreviations**: no "gonna", "wanna", "plz", "thx", "btw", "u", "ya", "rn", "nvm", "idk", "tbh", "lmk". Full words, correct spelling.
6. **Quantified proof uses verified wording**: Parhlai "reached 8,281 users and PKR 500,079 in booked revenue". Never ARR, never USD revenue, never annualized. The revenue itself is not claimed to be organic; acquisition was organic (SEO, Reddit, referrals).
7. **Short.** 60-400 words, direct fragments. One idea per sentence.
8. **No private data**: no phone number, no personal email; sign with `Hadi` + `hello@mhadi.dev`. Portfolio link: https://mhadi.dev
9. **Recipient-specific**: "Hey {Name}," when a public contact exists; fallback "Hey," otherwise. Reference the recipient's role when known.
10. **Nothing is sent from Mazdoor.** Drafts are copy-paste only. Use a public email only when found verbatim; otherwise use the sourced public profile or mark profile lookup required.

## Structure

```
Subject: Quick intro - Hadi Khan

Hey {Name},

I'm Hadi. Product Engineer.

[Specific hook: what pulled you to this company/job, or the role reference]

I also run Parhlai. 8,281 users. PKR 500,079 booked revenue. Built its AWS and Cloudflare stack, with infra near 1% of total spend.

{One evidence line for the family.}

The {job title} role at {company} looks close to that work.

More about me: https://mhadi.dev

Hope to talk to you :)

Hadi
hello@mhadi.dev
```

Automated lint lives in `mazdoor/outreach.py` (`lint_draft`) and runs in `mazdoor verify` over every generated draft.

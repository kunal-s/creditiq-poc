# Credit IQ Workbench

Build the FOUNDATION AND SHELL of CreditIQ, an identifier-to-CAM (Credit Appraisal Memorandum) automation platform for a commercial bank's wholesale and mid-market credit team. This is prompt 1 in a nine-prompt series and it builds the foundation only. Nothing is built yet. Add the functional spec document into your memory / knowledge for reference

Apply three global build rules on every screen, now and in every later prompt. Ships-as-real-product: production-feeling polish, a finished enterprise application, no wireframes, no lorem ipsum, no "coming soon". Connected and traversable: every entity and cross-reference is clickable, resolves to a real seeded record, and can be navigated back from; nothing is a dead end. AI woven in: a context-aware copilot and inline AI actions are present on every screen as part of the work, not bolted on.

Role of this section (internal, never rendered): this establishes the shell, the visual language, the seeded organisational context, and the navigation scaffold that every later section inherits. It must make a viewer feel they have opened a real, in-use credit workbench, not a demo.

Build the application shell and one reference screen, plus routed placeholder pages for every other screen.

Shell (persistent on all screens):

- Top bar: the CreditIQ mark on the left; the bank tenant shown as "Continental Commercial Bank, Corporate and Commercial Credit, West Region"; a global search; a copilot toggle on the right; and the signed-in user "Elena Rossi, Credit Analyst" with avatar and role.

- Left navigation, grouped: Workbench (Home, My Appraisals); Appraisal (New Appraisal, and the in-appraisal steps Identity, Data, Spread, Cross-Verification, Draft and Review, Submission); Portfolio (Memo Library); Governance (Audit and Examiner Walk-through); Admin (Template Designer, Ratio and Policy, Connectors and Consent, Users and Roles).

- Persistent appraisal-context strip: hidden on Workbench and Admin; when inside an appraisal it shows the active borrower, its masked identifiers, its stage in the pipeline, the assigned analyst, and the relationship manager. It is the spine that keeps the user oriented across appraisal steps.

Reference screen to fully build now: the Credit Workbench home (this is the primary screen of this prompt, must be the most polished, internally only, never labelled). Regions top to bottom:

- A greeting strip for Elena Rossi with three headline counters: appraisals in progress (4), awaiting my review (2), due this week (3).

- An "In-flight appraisals" table with real rows: Northwind Manufacturing Ltd, proposed Cash Credit enhancement INR 12.20 cr to INR 18.50 cr plus LC/BG INR 6.75 cr, stage Cross-Verification, relationship manager Marcus Chen, started 22 June 2026, risk first-cut CCB-4, one row visibly flagged with two open discrepancies; Aurora Foods Ltd, Cash Credit renewal INR 9.40 cr, stage Completed, rating CCB-2, completed 12 June 2026; plus two more plausible rows (a pharmaceutical distributor and an industrial packaging maker) in stages Data and Draft. Each borrower name links into that appraisal; each stage links to the matching step.

- A "Needs attention" panel listing the two Northwind discrepancies in one line each (turnover declared exceeds GST and bank credits; undisclosed recurring lender payment) and Northwind's annual review due 31 August 2026, each linking to where it is handled.

- A portfolio-at-a-glance strip: memos this month, average turnaround before and after CreditIQ, and a small rating distribution across the CCB-1 to CCB-8 grid.

- The copilot appears as a right-rail panel, context-aware to the Workbench, offering starting actions such as "start an appraisal", "summarise what needs my attention", and "what changed since Friday".

All other screens exist as routed placeholder pages that inherit the shell and state their name and one-line purpose, so navigation is fully traversable now and later prompts fill them in.

Seed data conventions: real specific names, identifiers, dates, and non-round amounts; consistent personas and terminology that recur across sections; a few in-progress and flagged states so it reads as authentic; every cross-reference points to a real seeded record. Identifiers are Indian (PAN, GSTIN) shown masked; regulatory framing is Indian.

Design principles to inherit on every screen: information density over decoration; real specific data over placeholders; color used for state, not ornament; consistent terminology; the seeded context felt on every screen; restrained clear primary and secondary actions; every linked entity clickable; the copilot present and context-aware.

What this section must prove (internal, never rendered): "This is a real, in-use credit workbench, and I already see the work waiting for me." The Credit Workbench home carries that.

Build to production-feeling polish, as a finished enterprise application. You own the components, libraries, and file structure; this prompt describes what it shows and does, not how to build it.

This project was built with [Lovable](https://lovable.dev).

## Build with Lovable

Continue developing this project in the [Lovable editor](https://lovable.dev/projects/a8f93fcf-db98-427e-91b0-c11c7dfcfaee).

- **Ship faster**: describe what you want to build and Lovable handles the code.
- **Stay in sync**: every change made in Lovable is committed straight to this repository.
- **Full ownership**: this code is yours. Push to `main` on GitHub and your changes sync back into Lovable, ready for your next prompt.

## Development

Prefer working locally? You need Node.js and npm — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
git clone <this-repository-url>
cd <repository-name>
npm i
npm run dev
```

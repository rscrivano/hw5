# Campus Customs Ops Desk: Dashboard Design (Problem 8)

The desk is where a human watches five AI teammates work the shop's tickets and signs off on any money that leaves the account. I designed it to feel like a **friendly back office for the same store** customers shop in, not a generic admin panel. It uses the same Campus Customs look as the HW4 storefront, laid out for operations.

Code: `frontend/src/` (`App.tsx` for state and polling; `components/` holds `TicketBoard`, `TeamRoom`, `RunRecap`, `LiveFeed`, `CashVault`, `Approvals` and `Drafts`; `styles.css` for the look).

---

## 1. Layout: one screen, three columns, left to right like the work itself

| Left: **Ticket board** | Center: **Team room → Run recap → Live feed** | Right: **Cash · Needs your OK · Drafts** |
|---|---|---|
| What needs doing | Who's doing it, and what they're saying | What it costs and what needs a human |

- **Why three columns:** a ticket's life reads left to right. Pick the work, watch the team, then approve the money. You never leave the page or open a modal to follow a run.
- **The left and right columns stay put** (sticky) while the feed scrolls, so the cash balance and the Approve buttons are always in view during a long run.
- **Narrower screens:** on a laptop the right column moves under the other two as cards; on a phone everything stacks into one column. I checked that nothing runs off the screen at 375px.

## 2. How the agents read differently

Each teammate has **one color, one emoji and one job line**, used everywhere they appear: their card, every feed line, recap cards and approval receipts. After a minute you can tell who is talking without reading the name.

| Agent | Look | Why |
|---|---|---|
| 🧢 **Boss** | Yale navy, full-width card on top | The manager sits above the team. Navy is the store's "authority" color |
| 📦 **Inventory** | Teal | Calm, stock-room green-blue |
| 🧾 **Accounting** | Sun gold | Money color, and it shares the gold of the cash gauge |
| 🏬 **Facilities** | Coral | Warm "building" color, distinct from the money colors |
| 💬 **Customer Service** | Violet | A softer, human color for the people-facing voice. Draft envelopes use the same violet |

- **Each agent shows its state.** Idle cards are faded. A *working* card gets a glowing border in its color, a bobbing avatar, typing dots and a 🔧 chip naming the tool it's using right now. *Done* cards show a check, and errors turn red.
- **Hand-offs are visible.** When Boss delegates, the receiving card pulses (a "baton pass"), the feed shows a pink hand-off line, and the recap draws the path (🧢 Boss ➜ 📦 Inventory …). You can see the team collaborate instead of just reading that it happened.
- **"Not needed this time"** lists the agents who sat a ticket out. This rewards lean runs: on ticket 102, Boss only calls Facilities, and the board shows that.
- **The feed is quiet by default.** Tool results are folded into a one-line "↳ result ▸" you can click to open, so the stream reads like a team chat, not a log dump. Reports back to Boss get a tinted card, and the end of a run gets a green 🏁 line.

## 3. How resolved tickets show up

- **Each ticket card has a status pill:** Open (blue), Team working… (sun yellow with a blinking dot and a moving shimmer across the card), or Resolved (green).
- **When a run finishes,** a green **RESOLVED** rubber stamp slams onto the card at an angle, the card gets a green wash, and the "x/3 resolved" counter in the header goes up. A toast confirms it.
- **The pill keeps the real detail:** "Resolved · waiting on your approval" or "Resolved · blocked". The team has finished its part, but the desk is honest that a human (or cash) still owns the next step.

## 4. How cash shows up

- **The vault card is the one dark, rich panel on the page** (a Yale navy gradient). That's on purpose: it's the most important number, so it's the heaviest thing to look at.
- **The balance is big and uses even-width digits** so it doesn't wobble as it changes. Under it are "Waiting for approval" and "If all approved". When pending requests would overdraw the account, the second number turns red and a warning explains that the pay step will refuse.
- **A gauge bar** shows the balance against the opening cash, with a ghost bar for what's left if everything pending is paid. You can see the cash squeeze on ticket 103 before anyone says it.
- **When you approve a payment,** the number counts down to the new balance over about a second, a pink "−$840.00" tag drops off the side, and the gauge shrinks. A toast says exactly what happened ("Paid $840.00 to Bulldog Print Co. Checking is now $160.00."). Cash only ever goes down, which matches the rules of the homework.

## 5. Approvals feel like signing a receipt

- **Each request is a paper receipt.** It has ticket-stub notches cut into the sides, a top stripe in the color of the agent who prepared it, the amount in large type, the payee, the agent's reason, and "Prepared by 🏬 Facilities".
- **"Approving as" is a name field,** remembered in the browser. The buttons stay disabled until a name is entered, so every payment row in the database records a real human's name (`payments.approved_by`).
- **Decided requests** collapse into a short list with PAID / REJECTED / REFUSED stamps, so you keep a paper trail on the page.

## 6. Creative touches that make it enjoyable

- **The Handsome Dan 🐶 brand mark and the rainbow stripe** from the storefront tie this back office to the shop customers already know.
- **Small rewards for real events:** the RESOLVED stamp slam, the baton pulse on hand-offs, and the cash countdown with its falling tag. Each one marks something that actually happened, so the motion carries information instead of decoration.
- **Warm, not sterile:** a cream background with soft color glows and a faint dot grid (the storefront's paper feel), rounded cards, and Inter in heavy weights for headings.
- **Drafts are envelopes** ✉️ that open into the letter, with "never sent" in the header. This is a reminder that nothing leaves the building.
- **Reset is safe.** It always asks first and explains what gets cleared (the audit trail is kept), and it's disabled while the team is working.
- **Accessible by default:** every motion turns off for people who set "reduce motion"; text meets contrast on every color; there are visible pink focus rings and labelled buttons; and the feed and toasts are announced to screen readers.

## 7. The Register: cash coming in (added after Problem 9)

- A **sun-yellow Register panel** sits under the approvals. Yellow is the money color the cash gauge already uses. Pick a ticket and the form prefills the customer, the quantity and the price Boss agreed (for example, $49 for the Yale AI Club), else the list price. It warns in red if a price is below cost.
- **Recording a sale** makes the vault count **up** with a green "+$28.00" tag, the mirror image of the pink tag for a payment. The vault now shows **Sales in** and **Paid out** side by side, plus whether the books tie out.
- **Deliveries on the way** lists ordered purchase orders with their ETA and a "Mark received" button, so stock goes up when the boxes actually arrive.
- Sales and receiving use the same "Approving as" name, so every cash movement, in or out, carries a person's name.

## 8. Built so it's easy to change

The colors are CSS variables at the top of `styles.css`. Each agent's color and emoji live in one file, `src/agents.ts`. Each panel is its own component. So "swap the columns", "make Accounting green", "hide tool results" or "put cash in the header" are each a small, contained edit.

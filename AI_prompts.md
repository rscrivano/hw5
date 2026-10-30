# AI Prompts Log: Homework 5 (Campus Customs Multi-Agent Operations)

This file logs the prompts typed into the vibe-coding session (Claude Code) for this assignment. New prompts are added at the bottom as the assignment goes on.

---

## Session 1 (first attempt)

The first session built the MCP server (`mcp_server/server.py`), the shared shop logic (`core/shop.py`), the FastAPI backend (`backend/`), the React dashboard (`dashboard/`), the reset script, and an offline smoke test. Portkey access was the main problem in that session. The exact prompt text from that session was not saved here.

---

## Session 2: Problems 1–3

### Prompt 2.1: Case background + Problems 1, 2, 3

> All matters of this conversation will be located in the following folder to contain this conversation in this file path: C:\Users\ryans\OneDrive - Yale University\Courses\Mgmt 409 AI\Homework\Homework 5. Some of the below steps may already be completed, don't duplicate them. Accessing the portkey appeared to be the main issue on the first attempt but you should be able to access it now.
>
> Here is the background of the case scenario:
> Campus Customs Multi-Agent Operations is the agentic team that runs the shop. Open tickets land on a board - customer orders, rent, unpaid bills, discount requests, anything the shop needs to handle. I will be building three pieces that talk to one-another: a MCP server, a FastAPI backend with a multi-agent team, and a React dashboard so that a human can watch the agents at work and approve the requests.
> The agent team has full connectivity being any agent can delegate tasks to any other agent for help. This assignment will build the following agents:
>
> * Boss - reads each ticket, decides who should work on it, and makes final calls
> * Inventory - checks stock by SKU and size, spots shortfalls, and figures out which vendor can restock
> * Accounting - watches cash and invoices, checks margins, and prepares payments or purchase orders for human approval
> * Facilities - handles the shop space side (leases, rent, etc.)
> * Customer Service - drafts messages for customers.
>
> Data - the data file exists under homework 5. This will be the original shop database and the tables include desk, tickets, inventory, pricing, vendors, leases, cash_accounts, payments, and invoices.
> The tools will update the database as tickets get resolved. Make a copy of the database file called data/campus_customs_new.db and point the MCP server and backend at the working copy. Keep the campus_customs.db untouched so I can reset when I want to restart resolving the tickets.
> Rules of the store:
>
> * The field desk.date_today is "today" for the shop. Use this date to determine what is overdue
> * Vendor lead times come from the vendors table
> * A vendor will not ship new product while they still have an open unpaid invoice
> * Human approval is required for any payments. Make sure this is done to avoid a loss in points for the assignment. if payment is made, ensure to update the relevant table
> * If there isn't enough cash, then the pay tool must refuse - no negative balances
> * Cash only goes out in this homework - we did not model revenue, so no money comes in
> * Before a full run to resolve the tickets, ensure to reset the database to the original values
> * Don't email customers or call real vendors. Drafts stay on the board
>
> Use my PORTKEY_API_KEY which is stored in the claude software, for AI calls. For this assignment, use only gpt-6-luna through Portkey for every agent. Multi-agent chats burn tokens fast. Points will be deducted if any other model shows up in the code or runs so be sure this is how it is approached.
>
> **Problem 1: Vibe coder prompts.** Create AI_prompts.md at the start of this assignment and keep this updated as I work through the assignment. This file is the log of what is typed in the vibe coder session here.
>
> **Problem 2: Study the Campus Customs database.** Open data/campus_customs.db and review through every table it has and the fields. Copy the original file to the data/campus_customs_new.db and later problems update that working copy so this is important. Study and ensure the three open tickets are understood so it can be made sense of how they link to other tables. Start output/harness.md. Now for every single table, list the fields and add a short line identifying/explaining why the table matters for the agents. The harness file will continue to grow in later problems here.
>
> **Problem 3: Build the MCP Server.** Write an MCP server in mcp_server by using the FastMCP. This will enable it to talk to data/campus_customs_new.db. I don't need you to connect or run this in the problem. Every agent in this homework assignment uses the tools in this MCP server which is why it's highly important. I will be adding more tools to it later and for now I will write three tools I know I will need for the tickets in the database. Keep the names clear and never invent any data, only use information that actually exists in the database. In output/harness.md, list each of the three MCP tools out clearly. For every tool, include: which table it reads, which specific ticket it serves the purpose of unlocking (101, 102, or 103), and one sentence on why that tool is the right one for that ticket. Make sure the lines are very clear and not vague, tie the tool to the ticket. Also add a short mcp_server/README.md file that explains in detail what the MCP server is intended for, which database file it uses, and the three tools it has.

### Prompt 2.2: Clarification (answer to Claude's question)

> Claude asked: the first attempt already built a 27-tool MCP server that the backend depends on; keep it or trim to three?
> **Answer:** Keep all, document 3. Leave the full server intact (the backend keeps working). The harness and README name the three ticket tools (`check_stock` → 101, `get_lease` → 102, `check_margin` → 103) as the Problem 3 tools and list the rest as later additions.

### Prompt 2.3: Status check

> So all 3 problems are complete now?

### Prompt 2.4: Match the Problem 3 wording

> Id rather match the wording of the instructions here so i am not out of line

Result: `mcp_server/server.py` was rewritten to have exactly three FastMCP tools (`check_stock`, `get_lease`, `check_margin`). The earlier 27-tool server was archived to `_archive/server_full_27_tools.py`.

### Prompt 2.5: Clarification

> wait so your saying now that its reduced to 3 tools it won't work later on?

Result: Claude explained that the trimmed server is not broken for later. The backend from the first attempt needs the full tool set, so it can't start until later problems add those tools back. The archive keeps them.

---

## Session 2 (continued): Problems 4–5

### Prompt 2.6: Problems 4 and 5

> Ok, Problem 4: Add the MCP Server to the vibe coder and test each tool
>
> add the MCP server to this project so that you, claude, can call the tools. Save the connection JSON text in .mcp.json at the project root (or however you save local MCP server lists.
>
> Now test each of the three MCP tools. Save the evidence of them being tested in output/mcp_smoke.json
>
> For every tool include the following:
> * the prompt that was asked of the vibe coder (claude)
> * the tool name
> * the tool output (must match values in data/campus_customs_new.db)
>
> Problem 5: Build the agent team and grow the MCP tools
>
> Now, build the agentic team for Campus Customs using PydanticAI: Boss, Inventory, Accounting, Facilities, and Customer Service. Make sure to include the prompts, models, and the agent loops so that they are able to delegate the work to one another with full connectivity to ensure full effectiveness.
>
> Put the agent prompts into the backend/prompts/ - one file per agent. Put the data types into the backend/models.py, and the agent files under the backend/ (the layout can vary if you see a better way of doing it as long as the five roles are clearly identified). Use my PORT_API_KEY and only the gpt-6-luna for each agent (i know i said that earlier but i wanted to make sure you remembered).
>
> Make sure the boss doesn't micro manage the employees and waste time or energy, but is applying energy effectively and looking at the macro-big picture of how the operation and tasks are being run. Don't overload specific agents, delegate effectively. For the Inventory employee, make sure they keep track effectively of the inventory by analyzing inventory at an appropriate amount of times and are able to put the purchase of restocking the inventory in with enough time in advance so things don't run fully out of stock. For the Accounting specialist, make sure to catch errors early on because we don't want to untie a bigger problem later and ensure that all items are properly being captured for their costs and revenue being generated. Make sure the books tie out monthly and that all overhead, SG&A, labor, COGS are accounted for, along with items below the EBITDA line which includes Interest, Taxes, Depreciation, and Amortization. For the Facilities professional, make sure they are ensuring all facilities are operating appropriately and are addressing problems in a timely manner to avoid customer experience issues dragging down revenue. For the Customer Service specialists, make sure the customers have a great experience, are taken care of promptly and with compassion, don't suck up to the clients, treat them with genuine respect and if issues arise then act appropriately and try to reduce the issue rather than make it worse.
>
> Add any tools the agents need to the MCP server so they can work on the open tickets. Shop facts come from the MCP server over the data/campus_customs_new.db - don't invent a second shop-tools layer that bypasses the MCP.
>
> Wire the agents so they append to output/audit_trail.json as they run: for each agent-loop step, record enough to audit later. Append to this file, don't wipe it each run.
>
> In output/harness.md, list each agent and each MCP tool (*including ones that I add in this problem) along with which table the tool uses. Also add a short safety section: the guardrails a real business would want when agents touch real customers and real money, plus limit that keep token use in check. Logically this would include but not be limited to a daily physical cash audit, inventory analysis, ensuring a great human experience that makes them want to come back to the store.
>
> Update mcp_server/README.md so the tool list matches what i have now

### Prompt 2.7: Clarification (answer to Claude's question about the virtual environment)

> Claude asked how to create the Python environment while OneDrive syncs the folder (pause OneDrive, or put the venv outside OneDrive).
> **Answer:** "it should be fixed now". Claude created `.venv` inside Homework 5.

---

## Session 2 (continued): Problem 6

### Prompt 2.8: Problem 6, plan the three tickets

> Don't do a full reset until I am done building the rest of these steps out.
>
> Problem 6: Plan the three tickets
>
> On each open ticket, the team should work together to apply their capabilities to resolve whatever the existing issue is. They should be able to effectively communicate with each other without wasting tokens to get the task/job done most effectively and have a high quality output. Build output/desk_tickets.html - a page that I can double-click with one tab per ticket (101, 102, and 103).
>
> Also add empty Cash and Reflection tabs for later problems (leave them blank or with a short "coming later" note for now).
>
> On each ticket tab, fill an Expected section only (leave room for an Actual selection I will fill after I run the agents).
>
> For each tickets Expected section, identify who the boss should call first in a given scenario (which should be logically determined by their area of expertise i explained earlier and who best aligns to the existing issue per their skills. All the agents delegations I expect are also noted earlier. Identify the MCP tools that make the most sense to run and use per the given situation, I trust your judgement.
>
> Plans that send every specialist on every ticket are not looked highly upon because they waste time and tokens.
>
> Compare this plan to what actually happens when the agents resolve the three tickets.

Result: `output/desk_tickets.html` was built with tabs for 101, 102, 103, Cash and Reflection. Each ticket tab has an Expected plan and an empty Actual / comparison table. The agents were not run and the database was not reset.

---

## Session 2 (continued): Problems 7–8

### Prompt 2.9: Backend routes and agent dashboard

> Problem 7: Backend routes
>
> The React frontend dashboard (the next problem) is going to need a backend it can call on. In backend/main.py, use FastAPI and add routes that do the following:
>
> * Return the three tickets and whether each is open or resolved
> * Take a ticket id and run the agent team on that ticket
> * Return recent agent events - what each agent said and which tools they used so the board can refresh
> * Approve a payment or purchase after a human clicks approve (agents only prepare the pay; this route is what actually changes cash)
> * Return the current checking balance from cash_accounts
> * Reset the database to the original values when I want to try a fresh run
>
> From the backend/ folder, start the server with: uvicorn main:app --reload --port 8000
>
> This turns on the backend at http://localhost:8000 so the frontend dashboard can call those routes.
>
> in output/harness.md, list each route in one line (what URL / what it does)
>
> Create the visual setup of the site to be more vibrant with better colors, similar to how we did the other storefront homework problem but make the design layout applicable to this case for what we are focused on.
>
> Problem 8: Agent dashboard
>
> Build the frontend dashboard in frontend/ with React + Vite + TypeScript. The page should call the routes I built in problem 7
>
> At the bare minimum here, the board should do the following:
>
> * List all three tickets
> * Let the customer pick one ticket and start the agent team on it
> * Show each agent and what they are saying / doing while the ticket runs
> * Mark a ticket resolved when the run finishes
> * Show a short summary of what each agent did on that ticket
> * Let a human approve a pay or purchase when asked
> * Show the checking balance (it should drop after an approved pay)
>
> Make the dashboard look good, like i explained in problem 7.
>
> Have the frontend here talk with the backend at http://localhost:8000. On the backend, allow the vite page origin (usually http://localhost:5173) so the browser is allowed to call those routes.
>
> npm run dev
>
> this opens the react desk in the browser so that I can pick tickets and watch agents. Write output/design.md with what I chose for the dashboard look (layout, how agents read differently, how resolved tickets and cash show up) and why, including creative choices that make it feel special and something humans like myself would actually enjoy using in real life.
>
> Set this up so I can review it and then direct you further on the layout of it all on changes I want to make

Result: `backend/main.py` (FastAPI) and `frontend/` (React + Vite + TS, styled like the HW4 storefront) were built. All testing used a scratch copy of the database, so the working DB was not reset or changed. Agents were switched to native structured output after Boss's free-text final answers ran into the token cap.

---

## Session 2 (continued): Problems 9–10

### Prompt 2.10: Problem 9, resolve the tickets

> This works well. I don't need any changes made that I can see.
>
> Problem 9: Resolve the tickets
>
> Before testing the agents on a full run over the three tickets, reset the working database data/campus_customs_new.db again so the start is clean. Note the starting checking balance. Then run all three tickets on the board (101, 102, 103) until each is resolved. Open output/desk_tickets.html from Problem 6. on each ticket tab, fill the Actual section from this run: which agents worked the task, what they delegated, and which tools they used. Keep the Expected section so that I can compare the two.
>
> On the Cash tab of the same output/desk_tickets.html, itemize the money:
>
> * Start checking balance (after the reset)
> * For each ticket: how cash changed when that ticket resolved, and why (which pay / purchase, dollar amount)
> * Ending checking balance - it must match cash_accounts in the working database
>
> Wrong cash math loses points even if the board shows every ticket resolved. Also save:
>
> * output/resolved_tickets.json - for each ticket: id, final status, short outcome, what each agent contributed, and any human approvals
> * output/resolved_board.html - a page I can double-click with a screenshot of the react board for each resolved ticket (101, 102, and 103)
>
> Append real runs to output/audit_trail.json. Finish output/harness.md so that it covers tables, MCP tools, the five agents, API routes, the dashboard, and safety rules.

Clarification: Claude asked who clicks Approve. **Answer:** "I'll approve myself". Follow-ups: "Approved #1", "Approved #1 now", "Done, approved". None of these clicks reached the backend (approval #1 stayed pending), so Claude fixed the silent disabled Approve button and a narrow-layout clip, and offered a browser or command-line way to approve.

### Prompt 2.11: Problem 10, reflection

> Problem 10: Reflection
>
> Open output/desk_tickets.html and fill the Reflection tab.
>
> * I would evaluate the performance of the agents on each ticket by assessing how many tokens it used, how long it took to figure out the problem resolution, the complexity level of the problem and if that justifies the length of time for the resolution
> * For each ticket, reflect upon how the actual vs expected turned out per the rationale I already expressed in this case development
> * If one agent had all the tools, the allocation of who to allocate the task to would have been easier but the actual energy output would have been longer and not as efficient.
>
> This is also part of that problem
>
> 3 new problems Campus Customs might face that this agent team could solve with the tools i built are financial forecasting based on transaction patterns within a specific period of time and utilize assumptions/predictability behind it, facility repair analysis and cost projections for wear and tear of the facility, and then effective management when unexpected issues arise the team hasn't faced before but is within their knowledge base collectively
>
> * 3 new problems Campus Customs might face that the agent team can't solve with these tools are: 1. HR complaint issues because no one is experienced there, how to address an electricity outage because they won't be supplied with electricity for the AI Agents anymore, understanding customer emotions fully because AI does not have real emotions even though it can try to understand it from a human lens based on its data
>
> * Make sure every answer i just answered is tied to this app and the three tickets i just ran. Use the ticket tabs and Cash tab on the same page as my evidence here.

Note: when this prompt arrived, only ticket 101's first pass had run and approval #1 was still pending. Claude ran tickets 102 and 103 to finish Problem 9 before writing the Reflection, so it could cite real evidence.

### Prompt 2.12: Connection errors

> fix this, there shouldn't be errors going on

Result: Claude found `ERR_CONNECTION_REFUSED` in the desk (the browser resolved "localhost" to IPv6 while uvicorn listens on IPv4) and switched the desk to `http://127.0.0.1:8000`.

### Prompt 2.13: Approvals and choice

> Approved both

(The database still showed both pending, and no approve request reached the backend.)

> Yes, fill as pending

Result: Claude filled the Actual, Cash and Reflection tabs in `output/desk_tickets.html`, built `output/resolved_tickets.json` and `output/resolved_board.html` (with `scripts/build_resolved_outputs.py`), and finished `output/harness.md`. Cash ends at $3,400.00, matching `cash_accounts`, with $3,240 pending approval.

### Prompt 2.14: Fix the issues

> no figure out how to fix these issues before i approve of everything

Result: Claude confirmed the desk accepts real typing and added `approve.bat`, a browser-free approval desk. Then the user's approvals landed (#1 $840 and #2 $2,400, approved by Ryan; cash $3,400 → $160).

Agent efficiency fixes:
- Ticket facts are loaded once and passed with every hand-off, so no agent re-reads the ticket.
- Boss rules: single-area tickets get one hand-off, Customer Service goes last with the facts, no repeat questions, and an offer the requester didn't name is recorded as `countered`.
- Specialists don't delegate back up the chain.

Scratch test from a fresh copy: 118,023 → 82,804 tokens (−30%). 102 used Boss→Facilities only (−52%); 103 followed the planned order and was countered (−34%).

Follow-up runs on the real board: 102 resolved; 101 requested PO #3 ($32, 4 tees); 103 requested PO #4 ($264) although only $160 was free. So purchase orders are now refused at request time when they don't fit in cash after pending requests, and Accounting's prompt says the same.

### Prompt 2.15: Decisions on #3 and #4

> Approve #3, reject #4

Result: the database still showed both pending, so Claude carried out Ryan's stated decision with the command-line approval desk (`backend.approve`, approver "Ryan"): #3 ($32 tee PO) was paid and #4 ($264 hoodie PO) was rejected. Cash went to $128.00. Closing runs: 101 ended blocked until stock arrives (2026-09-05) and 103 ended blocked on cash. Claude then updated the Actual, Cash and Reflection tabs, `resolved_tickets.json`, `resolved_board.html` (fresh screenshots) and `harness.md` with the final numbers.

### Prompt 2.16: Revenue question

> is revenue being recorder properly upon the sale of items to increase the cash amount and then properly decrease when inventory is purchased ?

Answer: purchases do decrease cash (payment #3, $32). Sales are not recorded, by design, because the homework rules say no revenue is modeled. There's no sales tool or table, and arriving purchase orders don't add stock yet.

### Prompt 2.17: Add sales tracking

> Add sales tracking

Result:
- **New table:** `sales`.
- **New human-only MCP tools:** `record_sale` (cash in, stock out, refuses below-cost and over-stock sales) and `receive_purchase_order` (stock in).
- **New read tools for agents:** `list_sales` and `list_purchase_orders`.
- **Books:** `books_tie_out` now checks opening + sales − payments = balance.
- **API routes:** `/api/sales`, `/api/purchase_orders`, `/api/purchase_orders/{id}/receive`, `/api/inventory`, `/api/pricing/{ticket_id}`.
- **Desk:** a Register panel, and the vault shows Sales in and Paid out.
- **Testing:** done on a scratch copy of the current data, in Python and through the desk UI. The real working DB is unchanged ($128, PO #1 still ordered).

### Prompt 2.18: Accounting status

> thats fine, don't waste tokens, but make note that in general that is something i would focus heavily on if i were running an actual business here and building it out. ALl other requirements i mentioned earlier are running though and its at least doing the accounting on a cash accrual basis now?

Result: Claude added an "Owner's note" to `output/harness.md` naming full accrual accounting as the top priority for a real business, and clarified that the system is cash-basis (not accrual).

---

## Session 2 (continued): Problem 11

### Prompt 2.19: Submit to GitHub

> Problem 11: submit to GitHub
>
> Push the code to a public GitHub repository so graders can clone it (my github account is live now on the edge browser). Submit the repo URL to canvas and also put it in output/github_url.txt
>
> Don't push the real .env to the GitHub repo. Do include both database files under the data/ (the original and your working copy) so the graders can run the app easily.
>
> This is the expected file layout in the image attached. (hw5/ with AI_prompts.md, requirements.txt, .env.example, .gitignore, .mcp.json, README.md, data/ (both DBs), mcp_server/ (server.py, README.md), frontend/, backend/ (main.py, models.py, prompts/ with the five agent prompts), output/ (harness.md, mcp_smoke.json, desk_tickets.html, design.md, resolved_tickets.json, resolved_board.html, audit_trail.json, github_url.txt))
>
> README should explain: copy original DB to the working copy when I need a clean run, start MCP server, start FastAPI backend, start the react board, reset the DB before a full three-ticket run

Result: public repo https://github.com/rscrivano/hw5 created and pushed (verified with a fresh clone: full layout, both DBs, no .env). The Canvas login needed the user, so Claude asked how to submit.

### Prompt 2.20: Submission zip

> can you put everything into a zip folder that is tied to this assignment so i can submit it on canvas? Include all the files in the zip that are part of this assignment development including the copy of the prompts here in Claude

Result: Claude built `hw5_submission.zip` (same files as the GitHub repo, plus a full export of this Claude Code session in `output/claude_session_transcript.md`, which is in the zip only and not on public GitHub).

# Browser practice table

Complete the [local setup](../README.md#local-setup), then run this command from the repository root.

```sh
.venv/bin/python -m app.web --port 8000
```

Open [the local table](http://127.0.0.1:8000), choose a starting seat and hand count, and start the session. MIT's check/call bot plays the other seat. The table rotates the button each hand.

Select an action. For a raise, enter the total chips you want to have contributed on this street. The preview displays the extra chips you will spend. Optionally explain your thinking, then choose **Commit move**. The review holds the position you saw when you chose. **Continue** reveals the opponent's response and the next decision or payout.

Refresh restores a pending decision or committed review while the local server runs. All tabs share one table. **End session** releases the referee worker and starter. Stop the server with Control-C.

For a repeatable demo, add `--seed 22`, start on the button, raise to 5, and check through showdown. K♠ J♣ wins 5 chips on this deal.

## Compare your choices with your bot

Start a ten-hand session and leave comparisons until the end if you want to play without hints. The MIT starter still plays the other seat. Your chart bot sits alongside you: it sees your cards and the same public betting position, but only your move reaches the referee. For immediate feedback, choose to see the comparison after committing. Switch comparison off to practice without recording recommendations.

After the last payout, finish the session to open the review. Start with a disagreement, or pick an agreed decision. Look at what you knew then: your cards, the board, action history, pot and price to call. Compare your reason with the bot’s rule. Two different moves count as a disagreement; two raises count when their totals differ by at least one big blind (2 chips).

For a repeatable example, launch with `--seed 72`, choose the button, play one hand, and raise the opening K5 offsuit to 5 chips. Your current chart folds that hand. The lesson is to ask which assumption about the opponent would justify opening it. The chart is your design choice. Outside chart spots, the policy samples equity against a uniform range. Neither result is a solver verdict or a calculation of the EV of your chosen line.

The journal lives on the local server. Refreshing the browser preserves it. Choosing **End session** early discards the session, including its journal. Starting another session or stopping the server also clears it.

## Reviewing the change

Look for the session and HTTP tests in `tests/test_web.py`. Run them with `.venv/bin/python -m pytest -q tests/test_web.py` in an environment that permits loopback sockets. Run the comparison checks with `.venv/bin/python -m pytest -q tests/test_comparison.py`. Solver comparisons and EV coaching belong to later milestones.

The [river exercise and optional coach](coach.md) explain the price of a call against different opponent ranges.

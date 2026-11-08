# Browser practice table

Complete the [local setup](../README.md#local-setup), then run this command from the repository root.

```sh
.venv/bin/python -m app.web --port 8000
```

Open [the local table](http://127.0.0.1:8000), choose a starting seat and hand count, and start the session. MIT's check/call bot plays the other seat. The table rotates the button each hand.

Select an action. For a raise, enter the total chips you want to have contributed on this street. The preview displays the extra chips you will spend. Optionally explain your thinking, then choose **Commit move**. The review holds the position you saw when you chose. **Continue** reveals the opponent's response and the next decision or payout.

Refresh restores a pending decision or committed review while the local server runs. All tabs share one table. **End session** releases the referee worker and starter. Stop the server with Control-C.

For a repeatable demo, add `--seed 22`, start on the button, raise to 5, and check through showdown. K♠ J♣ wins 5 chips on this deal.

## Reviewing the change

Look for the session and HTTP tests in `tests/test_web.py`. Run them with `.venv/bin/python -m pytest -q tests/test_web.py` in an environment that permits loopback sockets. The tested milestone covers human commitment, review and Continue. The silent comparison bot and coaching feedback belong to subsequent milestones.

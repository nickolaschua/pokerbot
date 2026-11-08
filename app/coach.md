# Review a decision in chips

Choose **Show EV math** on a committed comparison, or choose **Practice the saved river** at the table setup. In the saved exercise, commit to calling or folding before opening the numbers. Switch between a uniform range and the strongest hand from three independent random holdings to see how the answer changes.

The pot includes the bet you face. A call costing C into pot P breaks even at C / (P + C). Its incremental return is equity × (P + C) − C chips. A fold adds zero from this decision. River equity counts every legal opposing holding, including a half share for ties. On earlier streets the estimate assumes both players check through after this decision. Betting and raising also require a model of the opponent’s response.

**Explain this decision** works locally. To use an optional model, set `POKER_COACH_URL` to a trusted OpenAI-compatible chat-completions endpoint, `POKER_COACH_MODEL` to its model name and, if needed, `POKER_COACH_KEY` to its bearer token before starting the server. Clicking Explain sends that endpoint your recorded cards, board, action, written reason and computed facts. The model selects the facts to emphasize. The server supplies their wording and numerical values. A timeout or unusable reply returns the local explanation.

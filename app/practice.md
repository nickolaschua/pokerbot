# Play a practice hand

From the repository root, complete the Python environment and pinned engine setup in the [project README](../README.md). Then start a local session:

```sh
.venv/bin/python -m app.practice --hands 3 --position button --seed 42
```

The opponent runs MIT's original Python check/call starter in a separate subprocess. It connects to the referee over a local TCP socket. The practice worker waits for your input outside the bot's clock. Each prompt shows your cards, visible board, stacks, pot, legal moves and cost to call. Type `check`, `call`, `fold` or `raise 5` (total street contribution). Invalid input leaves the decision pending. Enter `quit` or send EOF to leave. A completed hand prints terminal acknowledgments and session bankrolls. The button rotates, and both stacks reset to 400 for the next hand.

For a reproducible one-hand demo, enter an illegal raise, a legal raise, then check through showdown:

```sh
printf 'raise 3\nraise 5\ncheck\ncheck\ncheck\n' |
  .venv/bin/python -m app.practice --hands 1 --position button --seed 42
```

The first command is rejected. The starter calls the five-chip raise. The flop pot is ten chips. On this deal Human wins five chips and Starter loses five. Use `--position bb` to start in the other seat. Omit `--seed` for ordinary random deals.

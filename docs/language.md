# Language decision

## Decision: Python for the first bot and experiment tools

There is no universally best poker language. Our immediate goal is to learn,
inspect decisions, and run reliable experiments. Python keeps that loop short.
The eval7 hand evaluator already runs compiled code, so this is not purely a
Python implementation of every expensive operation.

MIT supplies Python, Java, and C++ skeletons in its
[base engine](https://github.com/mitpokerbots/engine). This means choosing Python
now does not force a future solver to be written in Python.

| Choice | Best reason to choose it here | Cost |
| --- | --- | --- |
| Python | Clear experiments, probability work, rapid policy changes | Python loops can limit large searches and training |
| C++ | Large CFR traversals, detailed memory control, low-latency decisions; MIT skeleton exists | More build/debugging complexity and memory-safety responsibility |
| Rust | Native performance with strong memory-safety guarantees; interesting systems-learning project | We would implement/adapt the MIT protocol client and evaluator integration |
| Java | Already familiar with the JVM; MIT skeleton exists | No clear advantage for this particular first prototype |

These are engineering tradeoffs, not benchmarks claiming one language always wins.
If learning Rust or C++ becomes a primary goal, we can choose it deliberately.
For a poker-first project, Python is the default recommendation.

## When to change

1. Measure decision time and training throughput on a fixed workload.
2. Profile to identify the expensive function, rather than rewriting everything.
3. Try fewer allocations, caching, precomputation, and a better algorithm.
4. If it remains too slow for an explicit budget, port the hot path to C++ or
   implement a native bot using MIT's C++ skeleton.
5. Keep identical input/output fixtures and compare both correctness and speed.

Keep orchestration and reports in Python even if the policy or trainer becomes
native. A GPU is not needed for the current sampling/rule-based baseline.
Neural network experiments could change that; choose hardware after specifying
the workload and measuring it.

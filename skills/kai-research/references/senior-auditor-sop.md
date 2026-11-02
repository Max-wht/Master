# Private Auditor Reasoning

## Understand before judging

Explain each function's purpose in plain language: actor, inputs, state/value effect, intended guarantee, and dependencies. Identify where this explanation depends on an assumption rather than source evidence. Verify protocol intent using available documentation; distinguish missing intent from code defects.

## Explore forward and backward

Trace ordinary operation and work backward from a violated guarantee. Keep the attacker's perspective for exploit research; also examine operator error, bad configuration, key compromise, dependency failure, market stress, emergency recovery, and upgrades. Use concrete values for numerical and economic claims. Do not force non-exploit suggestions into attack narratives.

## Question and falsify

Ask what every important check assumes, who controls it, and what happens if the assumption fails. Deepen plausible attacks and independently try to refute them using guards, atomicity, compensating controls, supported inputs, and recovery. Neither defending the code nor defending a first impression is the goal.

## Assess changes in context

For a protection gap or recommendation, explain who benefits, what failure it addresses, how existing controls help, and its cost: operational latency, emergency response, compatibility, complexity, or maintenance. Missing multisig/timelock is not automatically a gap. Security-critical event omissions can be relevant when a specific monitor or recovery process depends on them; generic event completeness is not.

## Stop at the evidence boundary

Record inspected source/docs/tests and limitations. Turn unknown deployment facts and design decisions into precise questions with requested evidence. Continue other work. No quotas, automatic confidence promotion, or final severity at Kai stage.

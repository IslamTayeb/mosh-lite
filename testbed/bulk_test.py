#!/usr/bin/env python3
"""
Generate a sequence of states with efficient diffs for SSP testing.
"""

import random
import json

# Common words to build states from
WORDS = [
    "the",
    "be",
    "to",
    "of",
    "and",
    "a",
    "in",
    "that",
    "have",
    "it",
    "for",
    "not",
    "on",
    "with",
    "he",
    "as",
    "you",
    "do",
    "at",
    "this",
    "but",
    "his",
    "by",
    "from",
    "they",
    "we",
    "say",
    "her",
    "she",
    "or",
    "an",
    "will",
    "my",
    "one",
    "all",
    "would",
    "there",
    "their",
    "what",
    "so",
    "up",
    "out",
    "if",
    "about",
    "who",
    "get",
    "which",
    "go",
    "me",
    "when",
    "make",
    "can",
    "like",
    "time",
    "no",
    "just",
    "him",
    "know",
    "take",
    "people",
    "into",
    "year",
    "your",
    "good",
    "some",
    "could",
    "them",
    "see",
    "other",
    "than",
    "then",
    "now",
    "look",
    "only",
    "come",
    "its",
    "over",
    "think",
    "also",
    "back",
    "after",
    "use",
    "two",
    "how",
    "our",
    "work",
    "first",
    "well",
    "way",
    "even",
    "new",
    "want",
    "because",
    "any",
    "these",
    "give",
    "day",
    "most",
    "us",
    "system",
    "data",
    "network",
    "packet",
    "send",
    "receive",
    "state",
    "diff",
    "update",
    "sync",
    "protocol",
    "message",
]


def generate_states(num_states=1000, max_length=250, seed=42):
    """Generate a sequence of states with efficient diffs."""
    random.seed(seed)
    states = []

    # Start with a moderate-length initial state
    current_words = random.sample(WORDS, 15)

    for i in range(num_states):
        # Apply one of several edit operations
        op = random.choice(["add", "remove", "modify", "replace", "swap"])

        if op == "add" and len(" ".join(current_words)) < max_length - 20:
            # Add 1-3 words at a random position
            num_add = random.randint(1, 3)
            pos = random.randint(0, len(current_words))
            new_words = random.sample(WORDS, num_add)
            current_words = current_words[:pos] + new_words + current_words[pos:]

        elif op == "remove" and len(current_words) > 5:
            # Remove 1-2 words
            num_remove = min(random.randint(1, 2), len(current_words) - 5)
            pos = random.randint(0, len(current_words) - num_remove)
            current_words = current_words[:pos] + current_words[pos + num_remove :]

        elif op == "modify" and len(current_words) > 0:
            # Replace 1-2 existing words
            num_modify = min(random.randint(1, 2), len(current_words))
            for _ in range(num_modify):
                pos = random.randint(0, len(current_words) - 1)
                current_words[pos] = random.choice(WORDS)

        elif op == "replace" and len(current_words) > 3:
            # Replace a chunk of words with new words
            chunk_size = min(random.randint(2, 4), len(current_words) - 1)
            pos = random.randint(0, len(current_words) - chunk_size)
            new_words = random.sample(WORDS, chunk_size)
            current_words = (
                current_words[:pos] + new_words + current_words[pos + chunk_size :]
            )

        elif op == "swap" and len(current_words) > 1:
            # Swap two adjacent words
            pos = random.randint(0, len(current_words) - 2)
            current_words[pos], current_words[pos + 1] = (
                current_words[pos + 1],
                current_words[pos],
            )

        # Ensure we don't exceed max length
        state = " ".join(current_words)
        while len(state) > max_length and len(current_words) > 5:
            current_words.pop(random.randint(0, len(current_words) - 1))
            state = " ".join(current_words)

        states.append(state)

        # Occasionally reset to a moderately different state to add variety
        if i > 0 and i % 100 == 0:
            # Keep some overlap with current state
            keep = int(len(current_words) * 0.6)
            current_words = random.sample(current_words, min(keep, len(current_words)))
            current_words.extend(random.sample(WORDS, 10))

    # Make the last state transition back to first state smoothly
    # by incorporating some words from the first state
    if states:
        first_words = states[0].split()
        last_words = states[-1].split()
        # Mix in some words from the first state into the last
        overlap = min(5, len(first_words))
        bridge_words = first_words[:overlap] + last_words[overlap:]
        states[-1] = " ".join(bridge_words[: len(last_words)])

    return states


def main():
    print("Generating test states...")
    states = generate_states(num_states=1000, max_length=250)

    # Write to file
    output_file = "test_states.txt"
    with open(output_file, "w") as f:
        for state in states:
            f.write(state + "\n")

    # Print statistics
    print(f"Generated {len(states)} states")
    print(f"Saved to {output_file}")
    print(f"\nStatistics:")
    print(f"  Min length: {min(len(s) for s in states)} chars")
    print(f"  Max length: {max(len(s) for s in states)} chars")
    print(f"  Avg length: {sum(len(s) for s in states) / len(states):.1f} chars")

    # Sample a few states
    print(f"\nSample states:")
    for i in [0, 1, 2, len(states) // 2, len(states) - 2, len(states) - 1]:
        print(f"  State {i}: {states[i][:80]}{'...' if len(states[i]) > 80 else ''}")


if __name__ == "__main__":
    main()

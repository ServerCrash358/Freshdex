# Small, fixed golden set for the RAGAS eval (Section 4: "RAGAS eval --
# faithfulness/answer-relevancy against a golden Q&A set"). Kept small
# deliberately: each sample costs several judge-LLM calls (claim extraction,
# verification, question generation), and gemini-2.5-flash-lite's free tier
# is rate-limited (15 RPM) -- this is a demo-scale eval, not a benchmark
# suite.

GOLDEN_SET = [
    {
        "title": "Replication",
        "content": "Leader-based replication sends a stream of writes from the leader to followers, keeping replicas eventually consistent.",
        "question": "How does leader-based replication keep followers up to date?",
        "ground_truth": "The leader sends a stream of writes to its followers, which apply them to stay eventually consistent with the leader.",
    },
    {
        "title": "Sharding",
        "content": "Sharding splits a large dataset across multiple nodes so that each node stores only a subset of the data.",
        "question": "What is the purpose of sharding a dataset?",
        "ground_truth": "Sharding splits a large dataset across multiple nodes so each node only needs to store a subset of the data.",
    },
    {
        "title": "Consensus",
        "content": "Consensus algorithms like Raft and Paxos allow a cluster of nodes to agree on a single value even when some nodes fail.",
        "question": "What problem do consensus algorithms like Raft and Paxos solve?",
        "ground_truth": "They let a cluster of nodes agree on a single value even when some of the nodes fail.",
    },
    {
        "title": "Indexing",
        "content": "B-trees are the standard index structure used by most relational databases to support fast range queries and lookups.",
        "question": "What index structure do most relational databases use?",
        "ground_truth": "Most relational databases use B-trees as their standard index structure.",
    },
]

# Concurrency Strategies — Deep Dive

## Strategy Comparison

| Strategy | Thread-Safe | Oversell Risk | Throughput | Use Case |
|----------|:-----------:|:-------------:|:----------:|----------|
| **naive** | ❌ No | 🔴 High | 🟢 Highest | Demo / educational only |
| **lock** | ✅ Yes | 🟢 None | 🟡 Medium | Single-server, low contention |
| **atomic** | ✅ Yes | 🟢 None | 🟡 Medium | Single-server CAS pattern |
| **optimistic** | ✅ Yes | 🟢 None* | 🟡 Medium | Low-to-medium contention |
| **redis** | ✅ Yes | 🟢 None | 🟢 High | Distributed / multi-server |
| **queue** | ✅ Yes | 🟢 None | 🔴 Lowest | Max safety, audit-trail systems |

\* Optimistic may fail under very high contention (retries exhausted) but will never oversell.

---

## Strategy Details

### 🔴 naive
Plain global integer, zero synchronisation. Classic TOCTOU race condition — exists purely to show what goes wrong without protection.

### 🔒 lock
`threading.Lock()` wraps the check-and-decrement. Simple, correct, and the go-to solution for single-process servers.

### ⚛️ atomic
Implements a Compare-and-Swap (CAS) loop in Python. Mirrors the pattern used by `java.util.concurrent.AtomicInteger` and PostgreSQL's `SELECT FOR UPDATE`.

### 🔄 optimistic
Version-stamped dict: reads are lock-free; commits acquire a brief lock only to check-and-bump the version. Models JPA `@Version` / Hibernate optimistic locking. Retries up to 5× on conflict.

### 🟥 redis
Delegates to `redis.DECR` — a single atomic Redis command. The only strategy that works correctly across **multiple application servers**. Recommended for production.

### 📬 queue
Routes all purchases through a single background thread via `queue.Queue`. Eliminates concurrency at the purchase layer entirely. Highest safety, lowest throughput — ideal for financial ledgers.

---

## Sample Results

```
Mode: REDIS
Total Requests: 1000
Success:        10
Failed:         990
Final Stock:    0
Oversell:       false

Mode: NAIVE
Total Requests: 1000
Success:        ~47          ← varies per run (race condition)
Failed:         ~953
Final Stock:    ~-37         ← negative = oversold!
Oversell:       TRUE ⚠️

Mode: LOCK
Total Requests: 1000
Success:        10
Failed:         990
Final Stock:    0
Oversell:       false

Mode: QUEUE
Total Requests: 1000
Success:        10
Failed:         990
Final Stock:    0
Oversell:       false
```

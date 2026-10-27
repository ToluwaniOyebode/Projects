# Reliable background jobs

## Retries and idempotency
Network failures can leave a worker unsure whether an operation succeeded. Retrying the same request should reuse an idempotency key. Store the original result with the key and reject attempts to reuse it with a different payload. A retry must not charge a customer twice.

## Exponential backoff
A failed job can be scheduled again after a growing delay. Exponential backoff reduces pressure on a service that is recovering. Add jitter when many clients might retry together. Limit the number of attempts and route exhausted jobs to a dead-letter queue for inspection.

## Leases and worker crashes
A worker claims a job for a bounded lease. If it crashes, another worker can reclaim the job when the lease expires. Use a unique lease token so a late result from the old worker cannot overwrite the new owner's result. Delivery is at least once, so external side effects still need idempotency.

# Target State: Contracts and Schemas

## Contract Principles
- Every boundary uses typed payload contracts.
- Every schema has explicit versioning policy.
- Backward compatibility is declared, not assumed.

## Required Contract Domains
- Task dispatch (`TaskPacket` equivalent).
- Inter-agent envelope (`AgentMessage` equivalent).
- Worker result and error contracts (`result/meta`, `WorkerError`).
- EventBus event contract and signature metadata.

## Known Contract Gaps to Resolve in FA v3
- Clarify cascade-related output contract naming and ownership.
- Clarify energy-domain output contract for planned EnergyWorker.
- Reconcile schema registry claims across legacy docs before new additions.

## Acceptance Rule
No planned component moves to implemented state without at least one mapped input contract and one mapped output contract.

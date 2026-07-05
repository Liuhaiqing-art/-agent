"""Test client for Codex Clone API. Requires the server to be running."""

import httpx
import asyncio


async def main():
    base = "http://127.0.0.1:8000"

    async with httpx.AsyncClient(timeout=30) as client:
        # Test 1: Health
        print("=== Test 1: Health ===")
        r = await client.get(f"{base}/health")
        print(f"Status: {r.status_code}, Body: {r.json()}")

        # Test 2: Models
        print("\n=== Test 2: List Models ===")
        r = await client.get(f"{base}/models")
        data = r.json()
        print(f"Status: {r.status_code}, Models count: {len(data['models'])}")
        for m in data["models"]:
            print(f"  - {m['name']} ({m['provider']}): {m['capabilities']}")

        # Test 3: Empty requirement (validation)
        print("\n=== Test 3: Empty Requirement ===")
        r = await client.post(f"{base}/execute", json={"requirement": ""})
        print(f"Status: {r.status_code}, Detail: {r.json().get('detail')}")

        # Test 4: Execute with no API key (should fail gracefully)
        print("\n=== Test 4: Execute (no API key) ===")
        r = await client.post(f"{base}/execute", json={"requirement": "写一个二分查找"})
        data = r.json()
        print(f"Status: {r.status_code}")
        print(f"Task ID: {data.get('task_id')}")
        print(f"Status: {data.get('status')}")
        print(f"Error: {data.get('error', 'none')[:100]}")

        # Test 5: Task not found
        print("\n=== Test 5: Task Not Found ===")
        r = await client.get(f"{base}/task/nonexistent")
        print(f"Status: {r.status_code}, Detail: {r.json().get('detail')}")

        # Test 6: DAG model test (offline)
        print("\n=== Test 6: DAG Data Model ===")
        from codex.models import SubTask, TaskDAG
        dag = TaskDAG(tasks=[
            SubTask(id="1", description="task 1", dependencies=[]),
            SubTask(id="2", description="task 2", dependencies=["1"]),
            SubTask(id="3", description="task 3", dependencies=["1"]),
            SubTask(id="4", description="task 4", dependencies=["2", "3"]),
        ])
        print(f"Has cycle: {dag.has_cycle()}")
        topo = dag.topological_order()
        print(f"Topological levels: {[[t.id for t in level] for level in topo]}")
        print(f"Expected: [['1'], ['2', '3'], ['4']]")

        # Test 7: Cycle detection
        print("\n=== Test 7: Cycle Detection ===")
        dag_with_cycle = TaskDAG(tasks=[
            SubTask(id="1", description="t1", dependencies=["3"]),
            SubTask(id="2", description="t2", dependencies=["1"]),
            SubTask(id="3", description="t3", dependencies=["2"]),
        ])
        print(f"Has cycle: {dag_with_cycle.has_cycle()} (expected: True)")

        print("\n=== All tests completed ===")


if __name__ == "__main__":
    asyncio.run(main())

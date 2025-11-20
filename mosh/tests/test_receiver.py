import asyncio
from receiver import update_listener, init

async def main():
    init(53001)
    await update_listener()

if __name__ == "__main__":
    asyncio.run(main())

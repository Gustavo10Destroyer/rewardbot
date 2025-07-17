import aiohttp
import asyncio

# Configurações
OWNER = "Gustavo10Destroyer"
REPO = "rewardbot"
BRANCH = "main"
CHECK_INTERVAL = 60  # em segundos

async def get_last_commit() -> str | None:
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/commits/{BRANCH}"
    headers = {
        "Accept": "application/vnd.github+json",
        # "Authorization": "Bearer "
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                print(f"Erro ao acessar o GitHub: {resp.status}")
                return

            data = await resp.json()
            commit_sha = data["sha"]
            return commit_sha

async def git_pull():
    proc = await asyncio.create_subprocess_exec(
        "git", "pull",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    stdout, stderr = await proc.communicate()

    if proc.returncode == 0:
        print("Git pull concluído:")
        print(stdout.decode())
    else:
        print("Erro ao executar git pull:")
        print(stderr.decode())

async def loop_verificacao():
    last_commit = await get_last_commit()
    if last_commit is None:
        return

    while True:
        current_commit = await get_last_commit()
        if current_commit == last_commit:
            await asyncio.sleep(CHECK_INTERVAL)
            continue

        await git_pull()
        last_commit = current_commit
        await asyncio.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    asyncio.run(loop_verificacao())
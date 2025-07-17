import aiohttp
import asyncio

# Configurações
OWNER = "Gustavo10Destroyer"
REPO = "socket2"
BRANCH = "main"
CHECK_INTERVAL = 60  # em segundos

# Guarda o último commit conhecido
ultimo_commit = None

async def checar_commits():
    global ultimo_commit
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

            if ultimo_commit is None:
                ultimo_commit = commit_sha
                print("Inicializado com commit:", commit_sha)
            elif commit_sha != ultimo_commit:
                print("Repositório atualizado!")
                ultimo_commit = commit_sha
                # Aqui você pode colocar lógica pra reiniciar o bot ou baixar o novo código

async def loop_verificacao():
    while True:
        await checar_commits()
        await asyncio.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    asyncio.run(loop_verificacao())
import os

from dotenv import load_dotenv
load_dotenv()

import sqlite3
import discord
from datetime import datetime
from discord.ext import commands

# ===================== CONFIGURAÇÕES =====================
TOKEN = os.environ.get("TOKEN")
CUSTO_PADRAO = 5
GANHO_RECOMPENSA = 5
MOD_IDS = [591773451560419338, 1280365315519152203, 428154578932858880] #cca469,rick,gusta
MOD_CHANNEL_ID = 1387926300005503089 #  priv8 #registros

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# ===================== BANCO DE DADOS =====================
conn = sqlite3.connect("priv8.db")
conn.execute("PRAGMA foreign_keys = ON")
cursor = conn.cursor()
conn.commit()

# ===================== FUNÇÕES =====================
def add_points(user_id, amount):
    cursor.execute("INSERT OR IGNORE INTO users (user_id, points) VALUES (?, 0)", (user_id,))
    cursor.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()

def get_points(user_id):
    cursor.execute("SELECT points FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    return res[0] if res else 0

def has_consumed(user_id, content_id):
    cursor.execute("SELECT 1 FROM consumptions WHERE user_id = ? AND content_id = ?", (user_id, content_id))
    return cursor.fetchone() is not None

def register_consumption(user_id, content_id):
    cursor.execute("INSERT OR IGNORE INTO consumptions (user_id, content_id) VALUES (?, ?)", (user_id, content_id))
    conn.commit()

# ===================== VIEW PARA CONSUMIR =====================
class ConsumirView(discord.ui.View):
    def __init__(self, content_id: int, author_id: int, custo: int):
        super().__init__(timeout=None)

        # Validações básicas
        if custo < 0:
            raise ValueError("O custo do conteúdo não pode ser negativo.")

        self.content_id = content_id
        self.author_id = author_id
        self.custo = custo

        # Texto do botão (adaptável se for gratuito)
        label_text = (
            f"Consumir (-{self.custo} pontos)"
            if self.custo > 0 else
            "Consumir (Grátis)"
        )

        # Botão único com custom_id único
        self.add_item(discord.ui.Button(
            label=label_text,
            style=discord.ButtonStyle.primary,
            custom_id=f"consumir_button_{self.content_id}"
        ))


# ===================== VIEW DE APROVAÇÃO =====================
class AprovacaoView(discord.ui.View):
    def __init__(self, titulo: str, conteudo: str, autor_id: int, channel_id: int, custo: int = CUSTO_PADRAO):  # adiciona channel_id
        super().__init__(timeout=None)
        self.titulo = titulo
        self.conteudo = conteudo
        self.autor_id = autor_id
        self.channel_id = channel_id
        self.custo = custo

    def to_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="📬 Conteúdo aguardando aprovação",
            description=f"**{self.titulo}**",
            color=discord.Color.orange()
        )
        embed.add_field(name="ID do Autor", value=str(self.autor_id), inline=True)
        embed.add_field(name="Conteúdo", value=self.conteudo[:1024], inline=False)
        embed.add_field(name="Custo", value=f"{self.custo} pontos", inline=True)  # Mostrar custo
        embed.set_footer(text="Use os botões abaixo para aprovar, editar ou rejeitar.")
        return embed

    def _is_admin(self, user_id: int) -> bool:
        return user_id in MOD_IDS

    @discord.ui.button(label="✅ Aprovar", style=discord.ButtonStyle.success)
    async def aprovar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._is_admin(interaction.user.id):
            await interaction.response.send_message("❌ Você não tem permissão para isso.", ephemeral=True)
            return

        cursor.execute(
            "INSERT INTO contents (author_id, title, content, custo, status) VALUES (?, ?, ?, ?, 'aprovado')",
            (self.autor_id, self.titulo, self.conteudo, self.custo)
        )
        conn.commit()

        # Busca o ID do conteúdo inserido
        content_id = cursor.lastrowid

        # Enviar mensagem no canal original
        canal = bot.get_channel(self.channel_id)
        if canal is None:
            try:
                canal = await bot.fetch_channel(self.channel_id)
            except Exception:
                canal = None

        if canal is not None:
            view = ConsumirView(content_id, self.autor_id, self.custo)
            await canal.send(
                f"📦 Novo conteúdo disponível: **{self.titulo}**\nAutor: <@{self.autor_id}>\nClique abaixo para consumir (-{self.custo} pontos).",
                view=view
            )

        await interaction.response.edit_message(content="✅ Conteúdo aprovado e publicado!", view=None)

    @discord.ui.button(label="✏️ Editar", style=discord.ButtonStyle.secondary)
    async def editar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._is_admin(interaction.user.id):
            await interaction.response.send_message("❌ Você não tem permissão para isso.", ephemeral=True)
            return

        modal = EditarModal(self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="❌ Rejeitar", style=discord.ButtonStyle.danger)
    async def rejeitar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._is_admin(interaction.user.id):
            await interaction.response.send_message("❌ Você não tem permissão para isso.", ephemeral=True)
            return

        await interaction.response.edit_message(content="🚫 Conteúdo rejeitado pelos moderadores.", view=None)



class EditarModal(discord.ui.Modal, title="✏️ Editar Conteúdo"):
    def __init__(self, aprovacao_view: 'AprovacaoView'):
        super().__init__()
        self.view_ref = aprovacao_view

        self.titulo_input = discord.ui.TextInput(
            label="Novo Título",
            default=aprovacao_view.titulo,
            max_length=100
        )
        self.conteudo_input = discord.ui.TextInput(
            label="Novo Conteúdo",
            default=aprovacao_view.conteudo,
            style=discord.TextStyle.paragraph,
            max_length=2000
        )
        self.custo_input = discord.ui.TextInput(
            label="Custo do Poste (pontos)",
            default=str(aprovacao_view.custo),
            max_length=5  # Ajuste conforme quiser
        )

        self.add_item(self.titulo_input)
        self.add_item(self.conteudo_input)
        self.add_item(self.custo_input)

    async def on_submit(self, interaction: discord.Interaction):
        # Validar custo
        try:
            novo_custo = int(self.custo_input.value)
            if novo_custo < 0:
                raise ValueError("Custo não pode ser negativo.")
        except Exception:
            await interaction.response.send_message("❌ Custo inválido. Use um número inteiro não negativo.", ephemeral=True)
            return

        self.view_ref.titulo = self.titulo_input.value
        self.view_ref.conteudo = self.conteudo_input.value
        self.view_ref.custo = novo_custo

        # Atualiza embed da mensagem com custo atualizado
        try:
            await interaction.message.edit(embed=self.view_ref.to_embed(), view=self.view_ref)
        except Exception as e:
            print(f"Erro ao atualizar mensagem de aprovação: {e}")

        await interaction.response.send_message(
            "✅ Conteúdo e custo editados com sucesso. Agora você pode aprová-lo novamente.", ephemeral=True
        )



class EditarConteudoModal(discord.ui.Modal, title="✏️ Editar Conteúdo Pendente"):
    def __init__(self, pending_id: int, titulo: str, conteudo: str, custo: int):
        super().__init__()
        self.pending_id = pending_id

        self.titulo = discord.ui.TextInput(label="Título", default=titulo, max_length=100)
        self.conteudo = discord.ui.TextInput(label="Conteúdo", default=conteudo, style=discord.TextStyle.paragraph, max_length=2000)
        self.custo = discord.ui.TextInput(label="Custo (pontos)", default=str(custo))

        self.add_item(self.titulo)
        self.add_item(self.conteudo)
        self.add_item(self.custo)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            custo_int = int(self.custo.value)
            if custo_int < 0:
                raise ValueError("Custo negativo não permitido.")
        except ValueError:
            await interaction.response.send_message("❌ Custo inválido. Informe um número inteiro não negativo.", ephemeral=True)
            return

        cursor.execute(
            "UPDATE pending_contents SET title = ?, content = ?, custo = ? WHERE id = ?",
            (self.titulo.value, self.conteudo.value, custo_int, self.pending_id)
        )
        conn.commit()

        await interaction.response.send_message("✏️ Conteúdo editado com sucesso.", ephemeral=True)


# ===================== COMANDOS =====================
@bot.event
async def on_ready():
    print(f"🤖 Bot online: {bot.user}")
    cursor.execute("SELECT id, author_id, custo FROM contents")
    for content_id, author_id, custo in cursor.fetchall():
        bot.add_view(ConsumirView(content_id, author_id, custo))

@bot.command(name="help")
async def help(ctx):
    embed = discord.Embed(
        title="📚 Ajuda do Bot",
        description="Lista de comandos disponíveis:",
        color=discord.Color.blue()
    )
    embed.add_field(
        name="🪙 !pontos",
        value="Veja quantos pontos você tem.",
        inline=False
    )
    embed.add_field(
        name="📦 !postar <título> <conteúdo>",
        value="Envia um conteúdo para aprovação dos moderadores.\nEx: !postar ''conta premium'' user:admin senha:123 ",
        inline=False
    )
    embed.add_field(
        name="📈 !ranking",
        value="Exibe o ranking dos 10 usuários com mais pontos.",
        inline=False
    )
    embed.add_field(
        name="🛠️ !ponto <id> <valor>",
        value="**(Mod)** Adiciona ou remove pontos de um usuário.\nEx: `!ponto 123456789 10`",
        inline=False
    )
    embed.add_field(
        name="🔁 !reenviar_posts",
        value="**(Mod)** Reenvia todos os conteúdos já aprovados com botões de consumo.",
        inline=False
    )
    embed.add_field(
        name="📜 !last",
        value="**(Mod)** Mostra os últimos 10 consumos registrados.",
        inline=False
    )
    embed.set_footer(text="Comandos com **(Mod)** são disponíveis apenas para a administração")
    await ctx.send(embed=embed)

@bot.command()
async def pontos(ctx):
    pts = get_points(ctx.author.id)
    await ctx.send(f"{ctx.author.mention}, você tem **{pts} pontos**.")

@bot.command(name="ponto")
async def ponto(ctx, id: int, valor: int):
    if ctx.author.id not in MOD_IDS:
        await ctx.send("❌ Você não tem permissão para usar este comando.")
        return

    # Aplica os pontos
    add_points(id, valor)

    # Busca nome do usuário (caso possível)
    try:
        user = await bot.fetch_user(id)
        nome = f"{user.mention} ({user.name})"
    except:
        nome = f"ID: {id}"

    acao = "adicionados" if valor >= 0 else "removidos"
    embed = discord.Embed(
        title="🔧 Ajuste de Pontos",
        description=f"✅ Foram **{acao} {abs(valor)} pontos** para {nome}.",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

@bot.command()
async def last(ctx):
    if ctx.author.id not in MOD_IDS:
        await ctx.send("❌ Você não tem permissão para usar este comando.")
        return

    query = """
        SELECT c.user_id, c.content_id, ct.title, c.consumed_at
        FROM consumptions c
        JOIN contents ct ON c.content_id = ct.id
        ORDER BY c.consumed_at DESC
        LIMIT 10;
    """

    cursor.execute(query)
    rows = cursor.fetchall()

    if not rows:
        await ctx.send("Nenhum consumo registrado.")
        return

    msg = "**Últimos 10 consumos registrados:**\n"

    for user_id, content_id, title, consumed_at in rows:
        # 1. Tenta buscar o nome do usuário
        try:
            user = await bot.fetch_user(user_id)
            nome = f"{user.mention} ({user.name})"
        except Exception:
            nome = f"ID: {user_id}"

        # 2. Formatar data
        try:
            consumed_at = datetime.datetime.fromisoformat(consumed_at)
            consumed_str = consumed_at.strftime('%d/%m/%Y %H:%M')
        except Exception:
            consumed_str = str(consumed_at)

        # 3. Montar mensagem
        msg += f"- {nome} consumiu [{content_id}] **{title}** em {consumed_str}\n"

    await ctx.send(msg)


@bot.command()
async def postar(ctx, titulo: str, *, conteudo: str):
    # ✅ Validação básica
    if len(titulo) > 100:
        await ctx.send("❌ O título é muito longo (máx. 100 caracteres).")
        return

    if len(conteudo) < 10:
        await ctx.send("❌ O conteúdo é muito curto.")
        return

    mod_channel = bot.get_channel(MOD_CHANNEL_ID)

    if mod_channel is None:
        try:
            mod_channel = await bot.fetch_channel(MOD_CHANNEL_ID)
        except discord.NotFound:
            await ctx.send("❌ Canal de moderação não encontrado.")
            return

    # ⬇️ ✅ Agora passamos o canal original como argumento
    view = AprovacaoView(titulo, conteudo, ctx.author.id, ctx.channel.id, custo=CUSTO_PADRAO)

    embed = discord.Embed(
        title="📬 Novo conteúdo aguardando aprovação",
        description=f"**{titulo}**",
        color=discord.Color.orange()
    )
    embed.add_field(name="Autor", value=ctx.author.mention, inline=True)
    embed.add_field(name="ID do Autor", value=ctx.author.id, inline=True)
    embed.add_field(name="Conteúdo", value=conteudo[:1024], inline=False)
    embed.set_footer(text="Use os botões abaixo para aprovar, editar ou rejeitar.")

    try:
        await mod_channel.send(embed=embed, view=view)
    except discord.Forbidden:
        await ctx.send("❌ Não tenho permissão para enviar mensagens no canal de moderação.")
        return

    confirm_embed = discord.Embed(
        title="✅ Conteúdo enviado com sucesso!",
        description="Aguardando aprovação dos moderadores.",
        color=discord.Color.green()
    )
    await ctx.send(embed=confirm_embed)

    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass


@bot.listen("on_interaction")
async def consumir_button(interaction: discord.Interaction):
    custom_id = interaction.data.get("custom_id", "")
    if not custom_id.startswith("consumir_button_"):
        return

    try:
        content_id = int(custom_id.replace("consumir_button_", ""))
    except ValueError:
        await interaction.response.send_message("❌ ID inválido.", ephemeral=True)
        return

    # Consulta o conteúdo
    cursor.execute("SELECT author_id, content, custo FROM contents WHERE id = ?", (content_id,))
    row = cursor.fetchone()
    if not row:
        await interaction.response.send_message("❌ Conteúdo não encontrado.", ephemeral=True)
        return

    author_id, content_text, custo = row
    user_id = interaction.user.id

    # ✅ Autor sempre vê gratuitamente
    if user_id == author_id:
        await interaction.response.send_message(
            f"📘 Conteúdo (autor):\n{content_text}", ephemeral=True
        )
        return

    # ✅ Se já consumiu, mostra de novo (sem cobrar)
    if has_consumed(user_id, content_id):
        await interaction.response.send_message(
            f"📘 Conteúdo já consumido:\n{content_text}", ephemeral=True
        )
        return

    # ❌ Verifica pontos
    if get_points(user_id) < custo:
        await interaction.response.send_message(
            f"❌ Pontos insuficientes. Você precisa de {custo} pontos.", ephemeral=True
        )
        return

    # 💸 Cobra pontos e registra consumo
    add_points(user_id, -custo)
    register_consumption(user_id, content_id)

    await interaction.response.send_message(
        f"📘 Conteúdo consumido com sucesso:\n{content_text}\n\n💸 (-{custo} pontos)",
        ephemeral=True
    )

@bot.command()
async def reenviar_posts(ctx):
    if ctx.author.id not in MOD_IDS:
        await ctx.send("❌ Você não tem permissão para usar este comando.")
        return

    cursor.execute("SELECT id, author_id, title, content, custo FROM contents ORDER BY id ASC")
    posts = cursor.fetchall()

    if not posts:
        await ctx.send("⚠️ Nenhum conteúdo encontrado.")
        return

    await ctx.send(f"🔁 Reenviando {len(posts)} conteúdos aprovados...")

    for content_id, author_id, title, content_text, custo in posts:
        view = ConsumirView(content_id, author_id, custo)
        bot.add_view(view)

        embed = discord.Embed(
            title=f"📦 {title}",
            description="Clique no botão abaixo para consumir este conteúdo.",
            color=discord.Color.blue()
        )
        embed.add_field(name="Autor", value=f"<@{author_id}>", inline=True)
        embed.add_field(name="Custo", value=f"{custo} pontos", inline=True)
        embed.set_footer(text=f"ID: {content_id}")

        try:
            await ctx.send(embed=embed, view=view)
        except Exception as e:
            await ctx.send(f"⚠️ Erro ao reenviar conteúdo ID {content_id}: {e}")

@bot.command(name="ranking")
async def ranking(ctx):
    cursor.execute("SELECT user_id, points FROM users ORDER BY points DESC LIMIT 10")
    top_users = cursor.fetchall()

    if not top_users:
        await ctx.send("🏁 Ainda não há usuários com pontos registrados.")
        return

    embed = discord.Embed(
        title="🏆 Ranking de Pontos",
        description="Os 10 usuários com mais pontos no sistema:",
        color=discord.Color.gold()
    )

    for i, (user_id, points) in enumerate(top_users, start=1):
        try:
            user = await bot.fetch_user(user_id)
            nome = f"{user.mention} ({user.name})"
        except:
            nome = f"<ID: {user_id}>"
        embed.add_field(
            name=f"{i}. {nome}",
            value=f"🪙 {points:,} pontos",
            inline=False
        )

    embed.set_footer(text="Use !pontos para ver sua posição.")
    await ctx.send(embed=embed)

# ===================== INICIAR BOT =====================
bot.run(TOKEN)

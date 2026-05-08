import csv
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime

from rich.console import Console
from rich.table import Table

# --- CONFIGURAÇÕES ---
# Defina a URL raw do CSV (ex.: gist raw) ou deixe placeholder para usar só o arquivo local.
URL_CSV = os.environ.get("HORARIO_CSV_URL", "LINK_DO_SEU_GIST_AQUI")
ARQUIVO_LOCAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache_horario.csv")

console = Console()

_DATE_CELL = re.compile(r"^\d{2}/\d{2}$")


def limpar_nome_materia(texto):
    if not texto or len(texto.strip()) < 2:
        return ""
    texto = texto.strip()
    if _DATE_CELL.match(texto):
        return ""
    for marcador in ["Profº", "Profª", "Prof.", "\n", "\r"]:
        if marcador in texto:
            texto = texto.split(marcador)[0]
    texto = texto.strip()
    if "Ano" in texto or re.search(r"\b20\d{2}\b", texto):
        return ""
    return texto


def encontrar_linha_e_coluna_do_dia(dados, hoje):
    """Localiza a linha de cabeçalho de datas e o índice da coluna do dia."""
    melhor = (-1, -1, -1)  # row_idx, col_idx, score (nº de células dd/mm)
    for i, linha in enumerate(dados):
        limpa = [c.strip() for c in linha]
        if hoje not in limpa:
            continue
        score = sum(1 for c in limpa if _DATE_CELL.match(c))
        if score > melhor[2]:
            melhor = (i, limpa.index(hoje), score)
    row_idx, col_idx, _ = melhor
    return row_idx, col_idx


def _rotulo_e_intervalo(rotulo):
    r = rotulo.replace(" ", "")
    if "10:00-10:15" in r or "15:15-15:30" in r:
        return True
    return False


def _rotulo_e_almoco(rotulo):
    return "11:45" in rotulo and "13:00" in rotulo


def coletar_aulas_do_dia(dados, linha_cabecalho, col_dia):
    """Percorre apenas as linhas de grade (após o cabeçalho de datas)."""
    aulas = []
    for r in range(linha_cabecalho + 1, len(dados)):
        linha = dados[r]
        if not linha:
            continue
        rotulo_tempo = (linha[0] or "").strip()
        if not rotulo_tempo:
            if not any((c or "").strip() for c in linha[1:8]):
                continue
        if "DISCIPLINAS" in rotulo_tempo.upper():
            break
        celula = (linha[col_dia] if col_dia < len(linha) else "") or ""
        celula = celula.strip()
        aulas.append((rotulo_tempo, celula))
    return aulas


def baixar_csv_se_configurado():
    url = (URL_CSV or "").strip()
    if not url or "LINK_DO_SEU" in url or url == "LINK_DO_SEU_GIST_AQUI":
        return
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "monitor-horario/1.0"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
        with open(ARQUIVO_LOCAL, "wb") as f:
            f.write(data)
    except (urllib.error.URLError, OSError, ValueError) as e:
        console.print(f"[yellow]Aviso: não foi possível baixar o CSV ({e}). Usando cache local.[/yellow]")


def mostrar_tela():
    baixar_csv_se_configurado()

    if not os.path.exists(ARQUIVO_LOCAL):
        console.print("[red]Erro: cache_horario.csv não encontrado.[/red]")
        return

    hoje = datetime.now().strftime("%d/%m")

    try:
        with open(ARQUIVO_LOCAL, mode="r", encoding="utf-8", newline="") as f:
            dados = list(csv.reader(f))
    except OSError as e:
        console.print(f"[red]Erro ao ler {ARQUIVO_LOCAL}: {e}[/red]")
        return

    linha_hdr, col_dia = encontrar_linha_e_coluna_do_dia(dados, hoje)
    console.clear()
    if col_dia == -1:
        console.print(f"[bold red]Data {hoje} não encontrada no calendário do CSV.[/bold red]")
        return

    aulas = coletar_aulas_do_dia(dados, linha_hdr, col_dia)

    table = Table(
        title=f"📅 HORÁRIO - {hoje}",
        style="bold magenta",
        show_lines=True,
    )
    table.add_column("Horário", justify="center", style="yellow")
    table.add_column("Disciplina / Atividade", justify="left", style="white")

    for rotulo, celula in aulas:
        if not rotulo:
            continue
        u = celula.upper().strip()
        rotulo_u = rotulo.upper()

        if (
            "INTERVALO" in u
            or "INTERVALO" in rotulo_u
            or _rotulo_e_intervalo(rotulo)
        ):
            table.add_row(rotulo, "☕ INTERVALO", style="bold yellow")
        elif "ALMOÇO" in u or "ALMOCO" in u or _rotulo_e_almoco(rotulo):
            table.add_row(rotulo, "🍱 ALMOÇO", style="bold green")
        else:
            disciplina = limpar_nome_materia(celula) or celula.strip()
            if not disciplina:
                disciplina = "[dim]—[/dim]"
            if "RECESSO" in u or "CARNAVAL" in u or "FERIADO" in u:
                table.add_row(rotulo, disciplina, style="bold blue")
            else:
                table.add_row(rotulo, disciplina)

    if not aulas:
        console.print(f"[yellow]Nenhuma linha de horário encontrada para {hoje}.[/yellow]")
    else:
        console.print(table)
    console.print(f"\n[dim]Atualizado: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}[/dim]")


INTERVALO_ATUALIZACAO_SEG = 30 * 60  # 30 minutos

if __name__ == "__main__":
    while True:
        mostrar_tela()
        time.sleep(INTERVALO_ATUALIZACAO_SEG)

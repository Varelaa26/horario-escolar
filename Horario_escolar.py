import os
import time
import csv
import urllib.request
from datetime import datetime
from rich.console import Console
from rich.table import Table

# ==================== CONFIGURAÇÕES ====================
URL_CSV = "https://gist.githubusercontent.com/Varelaa26/63c44d77e5e8d9dab843ba80f5c384df/raw/26dfe77e131a4ff895002b5ebd9b4a968e98ae7d/cache_horario.csv"
ARQUIVO_LOCAL = "cache_horario.csv"
console = Console()

# Mapeamento do Horário com o índice exato da linha correspondente no seu CSV
HORARIOS_MAPEADOS = [
    {"hora": "07:30", "tipo": "Aula",      "linha_csv": 3},  # Linha 4 no Excel
    {"hora": "08:20", "tipo": "Aula",      "linha_csv": 6},  # Linha 7 no Excel
    {"hora": "09:10", "tipo": "Aula",      "linha_csv": 9},  # Linha 10 no Excel
    {"hora": "10:00", "tipo": "INTERVALO", "linha_csv": None},
    {"hora": "10:20", "tipo": "Aula",      "linha_csv": 12}, # Linha 13 no Excel
    {"hora": "11:10", "tipo": "Aula",      "linha_csv": 15}, # Linha 16 no Excel
    {"hora": "12:00", "tipo": "ALMOÇO",    "linha_csv": None},
    {"hora": "13:20", "tipo": "Aula",      "linha_csv": 18}, # Linha 19 no Excel
    {"hora": "14:10", "tipo": "Aula",      "linha_csv": 21}, # Linha 22 no Excel
    {"hora": "14:10", "tipo": "Aula",      "linha_csv": 24}, # Linha 25 no Excel (4ª tarde ou ajuste)
    {"hora": "15:00", "tipo": "Aula",      "linha_csv": 27}, # Linha 28 no Excel
    {"hora": "15:50", "tipo": "INTERVALO", "linha_csv": None},
    {"hora": "16:10", "tipo": "Aula",      "linha_csv": 30}, # Linha 31 no Excel
    {"hora": "17:00", "tipo": "Aula",      "linha_csv": 33}  # Linha 34 no Excel
]
# =======================================================


def baixar_csv_remoto():
    """Tenta baixar o CSV remoto. Primeiro tenta requests (se disponível),
    depois faz fallback para urllib. Retorna True se conseguiu salvar localmente."""
    try:
        import requests
        try:
            resp = requests.get(URL_CSV, timeout=10)
            if resp.status_code == 200:
                with open(ARQUIVO_LOCAL, "wb") as f:
                    f.write(resp.content)
                return True
        except Exception:
            pass
    except Exception:
        # requests não disponível, usa urllib
        pass

    # Fallback para urllib
    try:
        with urllib.request.urlopen(URL_CSV, timeout=10) as r:
            content = r.read()
            with open(ARQUIVO_LOCAL, "wb") as f:
                f.write(content)
            return True
    except Exception:
        return False


def limpar_nome_materia(texto):
    if not texto:
        return ""
    # Remove nome de professores e quebras de linha
    for marcador in ["Profº", "Profª", "Prof.", "\n", "\r"]:
        if marcador in texto:
            texto = texto.split(marcador)[0]

    texto_limpo = texto.strip().replace('"', '')
    # Ignora se for o cabeçalho da turma ou dados espúrios
    if "Ano" in texto_limpo or "2026" in texto_limpo or len(texto_limpo) < 2:
        return ""
    return texto_limpo


def mostrar_tela():
    if not os.path.exists(ARQUIVO_LOCAL):
        console.print("[bold red]Arquivo local cache_horario.csv não encontrado. Tentando baixar...[/bold red]")
        if not baixar_csv_remoto():
            console.print("[bold red]Falha ao baixar o CSV remoto. Verifique a conexão e tente novamente.[/bold red]")
            return

    try:
        with open(ARQUIVO_LOCAL, mode='r', encoding='utf-8') as f:
            dados = list(csv.reader(f))
    except Exception as e:
        console.print(f"[bold red]Erro ao ler o arquivo CSV: {e}[/bold red]")
        return

    # --- CONTROLE DE DATA DINÂMICO ---
    # Para testar com uma data fixa, defina a variável de ambiente TEST_DATE="dd/mm"
    hoje = os.environ.get("TEST_DATE") or datetime.now().strftime("%d/%m")

    coluna_hoje = -1
    for i, linha in enumerate(dados):
        linha_limpa = [c.strip() for c in linha]
        if hoje in linha_limpa:
            coluna_hoje = linha_limpa.index(hoje)
            break

    console.clear()
    if coluna_hoje == -1:
        console.print(f"[bold yellow]⚠️ Nenhuma coluna encontrada para o dia {hoje}.[/bold yellow]")
        return

    # --- CONSTRUÇÃO DA TABELA (detecção dinâmica de linhas de horário) ---
    import re

    table = Table(title=f"📅 PAINEL DE AULAS - DIA {hoje}", style="bold magenta", show_lines=True)
    table.add_column("Horário", justify="center", style="yellow", no_wrap=True)
    table.add_column("Disciplina / Atividade", justify="left", style="white")

    # Detecta linhas cujo primeiro campo parece um horário (ex: '07:45' ou '10:00 - 10:15')
    time_pattern = re.compile(r"^\s*\d{2}:\d{2}")

    for idx, row in enumerate(dados):
        if not row:
            continue
        first = row[0].strip()
        if not first:
            continue

        # Se o primeiro campo começa com hora, trata como linha de horário
        if time_pattern.match(first) or '-' in first:
            horario_label = first

            # Busca o conteúdo da célula do dia atual nessa linha
            materia_atual = ""
            if coluna_hoje is not None and coluna_hoje < len(row):
                celula = row[coluna_hoje].strip()
                materia_atual = limpar_nome_materia(celula)

            # Se não houver matéria, tenta detectar palavras-chave na própria linha
            if not materia_atual:
                joined = " ".join([c.strip() for c in row if c]).upper()
                if "ALMOÇO" in joined or "11:45" in horario_label:
                    materia_display = "🍱 ALMOÇO"
                elif "INTERVALO" in joined or "INTERVAL" in joined or '-' in horario_label:
                    materia_display = "☕ INTERVALO"
                elif joined.strip():
                    # mostra o conteúdo da própria linha (às vezes há texto na coluna de datas)
                    materia_display = limpar_nome_materia(row[coluna_hoje]) or "[dim]-- Aula Vaga --[/dim]"
                else:
                    materia_display = "[dim]-- Aula Vaga --[/dim]"
            else:
                materia_display = materia_atual

            table.add_row(horario_label, materia_display)

    console.print(table)
    console.print(f"\n[dim]Sincronizado: {datetime.now().strftime('%H:%M:%S')} | Modo: Tablet Integrado[/dim]")


if __name__ == "__main__":
    # Comandos do Termux são opcionais; executa apenas se disponíveis
    try:
        os.system("termux-wake-lock 2>/dev/null")
        os.system("termux-brightness 10 2>/dev/null")
    except Exception:
        pass

    try:
        while True:
            # Tenta atualizar o cache; não falha se não houver conexão
            baixar_csv_remoto()
            mostrar_tela()
            time.sleep(1800)
    except KeyboardInterrupt:
        try:
            os.system("termux-wake-unlock 2>/dev/null")
        except Exception:
            pass
        print("\nMonitor encerrado.")
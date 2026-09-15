# Configuração do projeto para o canal Nevil

Guia prático de configuração da WebUI (`http://localhost:8501`) pensado para o
objetivo do canal Nevil (cyber storytelling, evergreen, revisão humana
obrigatória). Contexto completo e decisões estratégicas: ver `CLAUDE.md`.

## 1. Abrir o painel

```
docker compose up -d --build webui
```
→ `http://localhost:8501`

## 2. LLM (roteiro) — ícone de engrenagem → aba "LLM Settings"

1. Dropdown **LLM Provider** → **DeepSeek**.
2. Cole a API key (platform.deepseek.com/api_keys).
3. Deixe **Base URL** e **Model Name** em branco — usa o default do projeto
   (`deepseek-v4-pro`, `https://api.deepseek.com`).

Para comparar com o Kimi (já configurado no endpoint Global): troque o mesmo
dropdown para **Kimi / Moonshot AI** e gere de novo com o mesmo Video Subject.

## 3. Roteiro ("Video Script Settings")

- **Video Subject**: o briefing do episódio.
- **Script Language**: `en-US` (já configurado — não mexer).
- Abra **"Advanced Script Settings"**:
  - **Script Paragraph Number**: 8-10 (dá espaço para as ~1.500-1.800 palavras
    alvo do roteiro de 10-12 min — ver `CLAUDE.md` seção 11).
  - **Custom System Prompt**: colar o System Prompt do canal (`CLAUDE.md`
    seção 11) — substitui o padrão inteiro, não soma.
  - **Custom Script Requirements**: colar os Requisitos personalizados
    (`CLAUDE.md` seção 11) — este soma ao System Prompt.
- Depois de gerar o texto, clique **"Generate Video Keywords"** e revise as
  keywords antes de seguir — se saírem genéricas, o b-roll também sai genérico.

## 4. Vídeo / B-roll ("Video Settings")

- **Video Source**: Pexels (já configurado com key).
- **Match Materials to Script Order**: **ligar** — mantém o b-roll na ordem
  narrativa em vez de aleatório.
- **Video Ratio**: Landscape (16:9) — master para YouTube/Bilibili.
- **Clip Duration** / **Clip Speed**: default (3s / 1.0x) para o primeiro teste.
- **Video Encoder**: "Default", a menos que haja GPU dedicada.
- Versão TikTok (9:16): rodar de novo com **Video Ratio = Portrait**, ou usar
  Opus Clip depois para reaproveitar cortes específicos do vídeo longo.

## 5. Voz ("Audio Settings")

**Rascunho grátis:**
- Voiceover Service → **"Azure TTS V1"** (na prática é o Edge TTS grátis, sem
  key — o nome na UI é só uma herança histórica do projeto).
- Escolher uma voz `en-US-*`.

**Produção final (persona do canal):**
- Voiceover Service → **"ElevenLabs TTS"**.
- Colar a API key (campo aparece ao selecionar o provider).
- Escolher a voz clonada/favoritada da biblioteca ElevenLabs.
- `model_id`: `eleven_multilingual_v2` por padrão; testar `eleven_v3` para mais
  qualidade de interpretação.

⚠️ Ao usar ElevenLabs, `subtitle_provider` **precisa** estar em `"whisper"` no
`config.toml` (não há esse controle na WebUI) — ElevenLabs não devolve timing
palavra-por-palavra, e o modo `"edge"` gera legenda mal sincronizada nesse
caso. **Já ajustado nesta configuração.**

## 6. Legenda ("Subtitle Settings")

- **Font**: `BeVietnamPro-Bold.ttf` (a única fonte bold do pacote pensada para
  alfabeto latino — o default `MicrosoftYaHeiBold.ttc` é chinês).
- **Position**: "Bottom".
- Cor/contorno: branco + contorno preto (default já funciona bem).

## 7. Trilha sonora ("Background Music")

- `"random"` a 20% de volume é um bom default neutro para o primeiro teste.
- Mais adiante, considerar `"Custom Background Music"` com uma faixa
  royalty-free fixa como identidade sonora do canal.

## 8. Publicação (Upload-Post + Bilibili)

⚠️ **Não existe botão de "Publicar" manual por vídeo na WebUI** — o upload só
dispara automaticamente logo após a geração, controlado pelas flags
`upload_post_auto_upload` / `bilibili_auto_upload`. Isso não bate com a regra
de revisão humana obrigatória em todo vídeo.

- Manter **`upload_post_auto_upload = false`** e **`bilibili_auto_upload =
  false`** sempre.
- Revisar o vídeo gerado (botão "Play" / "Open Task Folder" na tabela de
  tasks).
- Se aprovado, publicar manualmente em cada plataforma usando o arquivo da
  pasta da task, até que exista automação de "aprovar e publicar" separada da
  geração.
- Configurar credenciais mesmo sem automação ligada:
  - **Upload-Post**: adicionar `"youtube"` no multiselect de **Platforms**
    (hoje só tem `"tiktok"`).
  - **Bilibili**: preencher SESSDATA/bili_jct/buvid3 (DevTools → Cookies em
    bilibili.com) e o caminho da capa (`Bilibili Cover Image Path` —
    obrigatório).

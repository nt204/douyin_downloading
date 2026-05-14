# Douyin Translator

Web app tai video Douyin, trich xuat subtitle tieng Trung, dich sang tieng Viet bang Gemini, sau do burn subtitle vao file MP4.

## Stack

- FastAPI cho HTTP API
- Celery + Redis cho queue va worker
- yt-dlp de tai video/subtitle
- FFmpeg de convert subtitle va render video
- Gemini API la AI provider duy nhat cho dich subtitle

## Cau truc

- `backend/`: API, worker, services, utility
- `frontend/`: giao dien tinh
- `docker/`: Dockerfiles cho API va worker

## Chay local

1. Tao file `.env` tu `.env.example` va dien `GEMINI_API_KEY`.
2. Neu chay local bang `python` thay vi Docker, dat:

```env
YTDLP_COOKIES_FILE=runtime/cookies.txt
```

3. Khoi dong Redis:

```bash
docker compose up -d redis
```

4. Chay API va worker:

```bash
docker compose up --build
```

5. Mo `http://localhost:8000`.

## Kiem tra preflight

Truoc khi paste link Douyin, kiem tra runtime da du dieu kien:

```bash
python3 scripts/check_runtime.py
```

Neu dang chay Docker, co the goi:

```bash
curl http://localhost:8000/health/runtime
```

## API

- `POST /api/jobs`
- `GET /api/jobs/{job_id}`
- `GET /api/jobs/{job_id}/download`
- `GET /api/jobs/{job_id}/srt`
- `DELETE /api/jobs/{job_id}`
- `GET /health`

## Ghi chu van hanh

- He thong chi chap nhan URL `douyin.com`.
- Neu Douyin chan tai video, hay tao file `runtime/cookies.txt` va dat `YTDLP_COOKIES_FILE=/app/runtime/cookies.txt`.
- Neu video khong co subtitle TQ, job se bao loi. Khong co fallback AI khac ngoai Gemini.
- Job metadata va output file duoc luu trong `TEMP_DIR` va se bi xoa sau `MAX_FILE_AGE_HOURS`.
- Khi job loi o buoc download, thong diep `error` moi se noi ro host bridge hay `yt-dlp` dang fail o dau.

## Cookies Douyin trong Docker

1. Tao thu muc runtime:

```bash
mkdir -p runtime
```

2. Export cookies cua `douyin.com` tu browser thanh file Netscape format va luu thanh:

```bash
runtime/cookies.txt
```

3. Trong `.env`, de:

```env
YTDLP_COOKIES_FILE=/app/runtime/cookies.txt
```

4. Khoi dong lai stack:

```bash
docker compose down --remove-orphans
docker compose up --build -d
```

## Ghi chu cookies

- File `cookies.txt` phai dung Netscape format, moi dong du 7 cot tab-separated.
- Neu trong file co dong bi rong ten cookie, hay xoa dong do va export lai.
- `yt-dlp` co the van bi Douyin chan du da co cookie. Stack nay da chay them bridge Chromium trong Docker de fallback tu dong.
- Kiem tra bridge:

```bash
curl http://localhost:8765/health
```

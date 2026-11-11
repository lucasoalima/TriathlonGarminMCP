# API / demo do motor

## Rodar a demonstração da decisão do dia (sem app, sem Garmin, sem CNPJ)
Pré-requisito: Node.js. O `shared/dist` já vem compilado no zip.
```
cd packages/api
node server.mjs         # sobe em http://localhost:8787
# noutra aba:
curl http://localhost:8787/today
```
Retorna a decisão do dia (carga, prontidão sem HRV, treinos feitos, sessão modulada) calculada pelo motor a partir do MockDataSource (imita Health Connect).

Para recompilar o motor após mudar o `shared`: `npx tsc -p ../shared/tsconfig.build.json` e depois adicionar `.js` aos imports do dist (ver build no CLAUDE.md) — ou rode via `tsx`.

## Banco de dados (Prisma + PostgreSQL)
- Schema: `prisma/schema.prisma` (contas, consentimento, perfil, plano, atividades, wellness, carga, zonas, prontidão, agendamento).
- Setup: copie `.env.example` → `.env` (ajuste `DATABASE_URL`), depois:
```
npm install
npx prisma generate       # gera o client tipado
npx prisma db push        # cria as tabelas (dev)  — ou 'prisma migrate dev' com migrações
npx prisma studio         # inspecionar dados
```
- Enums em ASCII (ex.: `NATACAO`, `FORCA`, `GREEN_MINUS`); o app mapeia para exibição ("Natação", etc.).
- Tokens de conexão devem ser **criptografados em repouso** (LGPD).

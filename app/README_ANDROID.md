# Testar o Copiloto no Android

## Jeito mais rápido (sem instalar nada) — recomendado primeiro
1. Abra `app/www/index.html` no navegador do **celular** (ou mande o arquivo pra ele).
2. No Chrome do Android: menu ⋮ → **Adicionar à tela inicial**. Vira um "app" em tela cheia.
   > É a versão standalone (dados de exemplo embutidos — sem Garmin ao vivo ainda). Serve para testar a navegação e a cara.

## Jeito "app de verdade" no Android Studio (via Capacitor)
Pré-requisitos no seu PC: **Node.js LTS**, **Android Studio** (com Android SDK) e **JDK 17**.

Na pasta `app/`:
```
npm install
npx cap add android      # gera a pasta android/ (projeto do Android Studio)
npx cap sync
npx cap open android     # abre o projeto no Android Studio
```
No Android Studio: escolha um emulador ou o seu celular (com Depuração USB ligada) e clique **Run ▶**.

Sempre que mudar algo em `www/`, rode `npx cap sync` para atualizar o app.

## Observações
- Esta é a casca (UI) com dados de exemplo. A conexão real com o Garmin, login e IA no servidor entram depois (ver `docs/Escopo_Tecnico_MVP_Android.md`).
- `appId` = `com.copiloto.corpo` (em `capacitor.config.json`).

## Fonte de dados: Health Connect (Garmin)
- Plugin sugerido: `@kiwi-health/capacitor-health-connect` (`npm i @kiwi-health/capacitor-health-connect`), depois `npx cap sync`.
- No `AndroidManifest`, declarar as permissões de Health Connect (READ) para: ExerciseSession, HeartRate, SleepSession, OxygenSaturation, Steps.
- O usuário precisa ter o **Garmin Connect** instalado e sincronizando com o Health Connect.
- Código: `src/datasources/healthConnectMap.ts` (mapeamento puro, testado) + `src/datasources/healthConnect.ts` (chama o plugin — completar os TODOs com os nomes exatos da doc do plugin).
- Lembrete: via Health Connect **não vem HRV/estresse/Body Battery** (o motor já opera sem HRV).

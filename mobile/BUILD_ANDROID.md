# Copiloto do Corpo — build Android (Passo 2: Health Connect real)

App de uma tela (Decisão do Dia) que lê o **Health Connect no aparelho** (treino + sono + FC)
e calcula carga + prontidão on-device. Sem backend, funciona offline.

> **Mudou para Capacitor 7** — o plugin de Health Connect que lê treino+sono
> (`@kiwi-health/capacitor-health-connect`) exige Capacitor 7.

---

## 0) Requisitos
- **Android Studio** recente (2024.2+), que já traz **JDK 21** (o Capacitor 7 exige JDK 21).
- Celular Android **8.0+ (API 26+)** com **Health Connect** instalado e **Garmin Connect →
  Health Connect** ligado (Garmin Connect › Configurações › Health Connect › permitir FC, sono, treinos, SpO2). Sincronize.
- No emulador **não há dados do Garmin** → o app mostra exemplo. Dado real só no **celular físico**.

## 1) Migrar o projeto para Capacitor 7 (limpo)
Você já tinha rodado com Capacitor 6, então apague o que foi gerado e recomece:

**No PowerShell, dentro de `copiloto-app\mobile`:**
```powershell
Remove-Item -Recurse -Force android, node_modules -ErrorAction SilentlyContinue
Remove-Item -Force package-lock.json -ErrorAction SilentlyContinue
npm install
npx cap add android
npx cap sync android
```

Se o `npm install` reclamar de versões, rode `npm install` novamente; se persistir, `npm install --legacy-peer-deps`.

## 2) Ajustes obrigatórios no Android (uma vez)

### 2.1 minSdk 26
`android/variables.gradle` → `minSdkVersion = 26`

### 2.2 Permissões do Health Connect
`android/app/src/main/AndroidManifest.xml`, dentro de `<manifest>` (antes de `<application>`):
```xml
<uses-permission android:name="android.permission.health.READ_EXERCISE"/>
<uses-permission android:name="android.permission.health.READ_HEART_RATE"/>
<uses-permission android:name="android.permission.health.READ_SLEEP"/>
<uses-permission android:name="android.permission.health.READ_STEPS"/>
<uses-permission android:name="android.permission.health.READ_OXYGEN_SATURATION"/>
```
E, dentro da `<activity ... android:name=".MainActivity">`, o intent-filter que mostra a tela de
justificativa (senão o Android não abre o pedido de permissão):
```xml
<intent-filter>
  <action android:name="androidx.health.ACTION_SHOW_PERMISSIONS_RATIONALE"/>
</intent-filter>
```
Depois: `npx cap sync android`.

### 2.3 (Se der erro de JDK)
Android Studio → **Settings → Build, Execution, Deployment → Build Tools → Gradle** →
**Gradle JDK = 21** (jbr-21). Rode **File → Sync Project with Gradle Files**.

## 3) Rodar
```powershell
npx cap open android
```
No Android Studio: **Run ▶**.
- **Emulador (API 34):** abre com dados de exemplo (não tem Garmin). Serve para ver que compila/roda.
- **Celular físico (USB, depuração ligada):** na 1ª abertura o app pede as permissões do Health
  Connect → **conceder tudo**. Aí aparece o **seu dado real**: prontidão, carga (TSB/ACWR), sono e treinos de hoje.

## 4) Testar no treino
Treine → sincronize o Garmin Connect (ele escreve no Health Connect) → abra o Copiloto → veja a decisão do seu dia. Me traga onde bateu/errou.

## Onde está a fiação (implementado)
- `www/health-connect.js` — **HealthConnectDataSource**: pede permissão, lê `ExerciseSession`,
  `HeartRateSeries`, `SleepSession`, `Steps`, `OxygenSaturation` e monta o `CTX` do app.
- `www/engine.js` — o **motor** (`packages/shared`) empacotado para o browser (carga TRIMP/CTL/ATL/TSB/ACWR + prontidão).
- `www/index.html` — no Android chama `CopilotoHC.buildContext()`; **no emulador/web sem Health Connect**
  cai para `data/context.json` (ou o snapshot embutido). Regenerar o CTX de exemplo: `node tools/garmin-to-ctx.mjs`.
- Fluxo de dados no device: Health Connect → `aggregate()` → motor → `CTX` → render. Testável em Node: `node tools/test-health-connect.mjs`.

## Notas
- Sem HRV (o Garmin não escreve HRV no Health Connect) → prontidão por **sono + carga** (pesos recalibrados);
  o card mostra "HRV —" e os chips se ajustam sozinhos.
- FC repouso/máx **estimados das amostras** lidas (mín/máx observados; fallback 60/190). Puxar do perfil depois.
- FC detalhada é lida só nos **últimos 14 dias** (volume); sessões mais antigas entram na carga por duração+esporte.
- O proxy nativo é obtido via `Capacitor.registerPlugin('HealthConnect')` (não precisa de bundler no `www`).
- Se a tela de permissão do Health Connect não abrir, confira o intent-filter (2.2) e veja o README do
  plugin `@kiwi-health/capacitor-health-connect` (pode pedir um `activity-alias` extra em Android 14+).
- Emulador com "exemplo" é esperado. Erros de build: copie o Logcat/Build Output e me mande.

; Ajouts INJARA à l'installeur NSIS d'electron-builder.
;
; Le moteur d'analyse (torch) a besoin du runtime Microsoft Visual C++ 2015-2022 (x64). S'il manque, on installe en
; silence vc_redist.x64.exe, embarqué dans l'installeur (téléchargé et vérifié par scripts/preparer-installeur.mjs).
; L'installeur tourne en administrateur (nsis.perMachine) : vc_redist peut donc s'installer sans autre demande.
; En cas d'échec, INJARA s'installe quand même : seul le critère « adéquation globale » sera désactivé.

!macro customInstall
  SetRegView 64
  ReadRegDWORD $0 HKLM "SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64" "Installed"
  SetRegView lastused
  ${If} $0 != 1
    DetailPrint "Installation du runtime Microsoft Visual C++ 2015-2022 (x64)..."
    InitPluginsDir
    File "/oname=$PLUGINSDIR\vc_redist.x64.exe" "${BUILD_RESOURCES_DIR}\vc_redist.x64.exe"
    ExecWait '"$PLUGINSDIR\vc_redist.x64.exe" /install /quiet /norestart' $1
    Delete "$PLUGINSDIR\vc_redist.x64.exe"
    ; 0 : installé ; 3010 : installé, redémarrage conseillé ; 1638 : une version plus récente est déjà là
    ${If} $1 != 0
    ${AndIf} $1 != 3010
    ${AndIf} $1 != 1638
      MessageBox MB_ICONEXCLAMATION|MB_OK "Le runtime Microsoft Visual C++ n'a pas pu être installé (code $1).$\r$\n$\r$\nINJARA fonctionnera, mais sans le critère « adéquation globale ». Installez-le ensuite depuis https://aka.ms/vs/17/release/vc_redist.x64.exe puis relancez INJARA."
    ${EndIf}
  ${EndIf}
!macroend

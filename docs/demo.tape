# LanYin demo tape — the 10-minute happy path (m1 milestone).
# Renders to assets/demo.gif. Drives the real `lanyin` binary; no API key needed
# (voice lock needs MINIMAX_API_KEY, so the demo seeds a locked profile and
# shows `voice show`, plus the honest m2/m3 roadmap messages).
# Re-render on demand: `vhs docs/demo.tape` (CI: .github/workflows/demo.yml).

Output assets/demo.gif
Set Width 1200
Set Height 600
Set FontSize 16
Set Padding 24
Set Theme "Dracula"
Set TypingSpeed 0.02

Hide
Type "REPO=$(pwd)"
Enter
Type "DEMO=/tmp/lanyin-demo && rm -rf $DEMO && mkdir -p $DEMO && cd $DEMO"
Enter
Show

Type "lanyin --version"
Enter
Sleep 800ms

Type "lanyin --help"
Enter
Sleep 1s

Type "lanyin init 硅谷早茶 --platform xiaoyuzhou"
Enter
Sleep 1s

Type "cat lanyin.toml"
Enter
Sleep 700ms

Type "mkdir -p .lanyin && cp $REPO/examples/voice-lock.sample.json .lanyin/voice-lock.json"
Enter
Sleep 500ms

Type "lanyin voice show"
Enter
Sleep 1s

Type "cp $REPO/examples/ep01.md ."
Enter
Sleep 400ms

Type "lanyin add ep01.md"
Enter
Sleep 1s

Type "lanyin build ep01.md"
Enter
Sleep 1s

Type "lanyin export rss --platform xiaoyuzhou"
Enter
Sleep 1s

Type "# m1 done: voice locked, episodes registered. m2 build + m3 export ship next."
Enter
Sleep 2s

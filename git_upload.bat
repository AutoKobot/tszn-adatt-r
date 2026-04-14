@echo off
echo [EduRegistrar] GitHub feltöltés indítása...
git add .
git commit -m "Phase 3 finalized: Finance, Compliance, Smart Assistant, and Autocomplete features"
echo [EduRegistrar] Feltöltés a szerverre (Push)...
git push
echo.
echo [KESZ] Minden valtozas feltoltve a GitHubra!
pause

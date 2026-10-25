#!/bin/sh
# Смоук-тест: вставки, параллельные вставки, удаление, сверка на всех нодах
A=${API:-http://localhost:8000}
j='-H Content-Type:application/json'
curl -s $A/health; echo
curl -s $j -d '{"pos":0,"text":"Hello world"}' $A/insert; echo
curl -s $j -d '{"pos":5,"text":", dear"}' $A/insert; echo
# две параллельные вставки в одну позицию
curl -s $j -d '{"pos":0,"text":"[A]"}' $A/insert & curl -s $j -d '{"pos":0,"text":"[B]"}' $A/insert & wait; echo
curl -s $j -d '{"pos":0,"length":3}' $A/delete; echo
for n in 0 1 2 3; do curl -s "$A/document?node=$n"; echo; done
curl -s $A/status; echo

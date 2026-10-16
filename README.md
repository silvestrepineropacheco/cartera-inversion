# Cartera de inversión (skill para Claude)

Una skill para [Claude Code](https://claude.com/claude-code) que funciona como **tutor y asistente para armar, entender y seguir una cartera de inversión desde Argentina**, pensada para alguien que **nunca invirtió**.

No te dice "comprá esto". Te enseña cómo funciona cada cosa, te ayuda a definir tu perfil, te muestra modelos de cartera de ejemplo y te acompaña en el día a día para que sigas tu propio plan sin decisiones impulsivas.

> ⚠️ **Material educativo, no asesoramiento financiero.** Leé el [aviso legal](AVISO_LEGAL.md) antes de usarla.

## Qué hace

| Función | Descripción |
|---|---|
| **Enseña en criollo** | CEDEARs, bonos, ON, FCI, dólar MEP, ETFs, diversificación, riesgo, interés compuesto, cómo abrir cuenta en un bróker |
| **Perfil de inversor** | Cuestionario de 6 preguntas → conservador, moderado o agresivo |
| **Modelos de cartera** | Distribuciones de ejemplo por clase de activo (liquidez, renta fija en pesos y en dólares, acciones internacionales y argentinas) con el porqué de cada parte |
| **Chequeo antes de comprar** | Compara la compra con tu plan y responde **OK / REVISAR / NO**: categoría fuera del plan, topes de concentración, falta de motivo, montos chicos, recompras después de vender con pérdida |
| **Registro de la cartera** | Compras y ventas con su motivo, lotes FIFO, valuación en pesos y dólares, plata puesta vs. valor actual |
| **Aporte mensual** | Reparte la plata nueva entre lo que quedó atrasado, sin vender |
| **Rebalanceo** | Muestra qué categorías se salieron de la banda y cuánto ajustar, con la ganancia sin realizar de cada activo |
| **Revisión semestral** | Estado OK / ATENCIÓN / REVISAR y preguntas guía. Nunca vende sola |
| **Diario y resultados** | Por qué compraste cada cosa, evolución en el tiempo y resultados realizados por año |

Los datos regulatorios e impositivos de Argentina cambian seguido; la skill le pide a Claude que los verifique antes de darlos como vigentes.

## Requisitos

- [Claude Code](https://claude.com/claude-code)
- Python 3.8 o superior (solo biblioteca estándar, no hay que instalar paquetes)
- No necesita API keys ni cuentas en ningún servicio. Los precios los cargás vos (o Claude los busca).

## Instalación

Cloná el repositorio dentro de tu carpeta de skills personales:

```bash
git clone https://github.com/silvestrepineropacheco/cartera-inversion.git ~/.claude/skills/cartera-inversion
```

En Windows, `~` es tu carpeta de usuario (`C:\Users\<tu usuario de Windows>`). También podés descargar el ZIP desde GitHub y descomprimirlo en `~/.claude/skills/cartera-inversion/`.

Abrí una sesión nueva de Claude Code y listo.

## Uso

Hablale a Claude con naturalidad:

- *"Quiero empezar a invertir y no sé nada"*
- *"Ayudame a armar mi cartera"*
- *"¿Me conviene comprar AAPL con $50.000?"*
- *"Compré 10 CEDEARs de SPY a $35.000, cargalo"*
- *"Este mes tengo $200.000 para invertir, ¿cómo los reparto?"*
- *"¿Cómo va mi cartera?"*

O llamala directo con `/cartera-inversion`.

### El script por dentro

Claude usa `scripts/cartera.py`, que también podés correr a mano:

```bash
python scripts/cartera.py init --perfil moderado --moneda-base USD --tipo-cambio 1200 \
  --objetivo "Liquidez=10" "Renta fija pesos=15" "Renta fija dolares=35" "Acciones internacionales=35" "Acciones argentinas=5"
python scripts/cartera.py chequear SPY --monto 350000 --moneda ARS --categoria "Acciones internacionales" --tipo etf --motivo "Base de la cartera"
python scripts/cartera.py compra SPY --categoria "Acciones internacionales" --tipo etf --cantidad 10 --precio 35000 --moneda ARS --motivo "Base de la cartera"
python scripts/cartera.py estado
python scripts/cartera.py aporte 200000 --moneda ARS
python scripts/cartera.py rebalanceo
python scripts/cartera.py revision
python scripts/cartera.py --help        # todos los comandos
```

Tu cartera se guarda en `~/cartera-inversion/cartera.json`, **fuera de esta carpeta**, así nunca se sube a GitHub por error. Podés cambiar la ruta con la variable de entorno `CARTERA_ARCHIVO` o con `--archivo`.

## Estructura

```
cartera-inversion/
├── SKILL.md                 # instrucciones para Claude
├── scripts/cartera.py       # seguimiento, aportes, rebalanceo, chequeos
└── references/
    ├── conceptos.md         # glosario en criollo
    ├── perfil.md            # cuestionario de perfil
    ├── modelos.md           # modelos de cartera por perfil
    └── argentina.md         # instrumentos, brókers, MEP, CEDEARs, impuestos
```

## Créditos

Algunas ideas (topes de concentración, chequeo antes de operar, diario de motivos, revisión periódica sin ventas automáticas, lotes FIFO) se inspiraron en estos proyectos con licencia MIT, adaptadas para principiantes en Argentina. El código es propio.

- [tradermonty/claude-trading-skills](https://github.com/tradermonty/claude-trading-skills)
- [Jakeschincariol/trader-skill](https://github.com/Jakeschincariol/trader-skill)

## Licencia

[MIT](LICENSE). Usala, modificala y compartila libremente.

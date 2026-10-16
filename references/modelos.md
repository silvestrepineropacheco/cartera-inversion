# Modelos de cartera educativos

Son puntos de partida típicos para cada perfil, pensados para alguien en Argentina que ahorra en pesos y en dólares. No son recomendaciones personales: la persona puede mover los porcentajes y es ella quien decide. Explicá el porqué de cada parte, que es lo que realmente sirve.

## Las clases de activo

| Categoría | Para qué está | Ejemplos (ver `argentina.md`) |
|---|---|---|
| **Liquidez** | Plata disponible en el día, sin sobresaltos | FCI money market en pesos o dólares, caución |
| **Renta fija pesos** | Cubrirse de la inflación en pesos a corto/mediano plazo | Plazo fijo UVA, Lecaps, bonos CER, FCI de renta fija en pesos |
| **Renta fija dólares** | Ingresos en dólares con menos volatilidad que las acciones | Obligaciones negociables (ON) de empresas, bonos soberanos (GD30, AL30), FCI en dólares |
| **Acciones internacionales** | El motor de crecimiento a largo plazo, diversificado y en dólares | CEDEARs de ETFs amplios (SPY, QQQ, VT, EEM, etc.) |
| **Acciones argentinas** | Exposición a la economía local; más riesgo y volatilidad | Acciones del Merval, FCI de acciones argentinas |

## Modelos

| Categoría | Conservador | Moderado | Agresivo |
|---|---|---|---|
| Liquidez | 20 % | 10 % | 5 % |
| Renta fija pesos | 25 % | 15 % | 5 % |
| Renta fija dólares | 40 % | 35 % | 20 % |
| Acciones internacionales | 15 % | 35 % | 60 % |
| Acciones argentinas | 0 % | 5 % | 10 % |

Comando `init` para cada uno:

```bash
# Conservador
--objetivo "Liquidez=20" "Renta fija pesos=25" "Renta fija dolares=40" "Acciones internacionales=15"
# Moderado
--objetivo "Liquidez=10" "Renta fija pesos=15" "Renta fija dolares=35" "Acciones internacionales=35" "Acciones argentinas=5"
# Agresivo
--objetivo "Liquidez=5" "Renta fija pesos=5" "Renta fija dolares=20" "Acciones internacionales=60" "Acciones argentinas=10"
```

## Ideas para explicar

- **Por qué no todo en acciones**: las acciones crecen más a largo plazo pero pueden caer 30–50 % en una crisis. La renta fija amortigua esas caídas y da plata para comprar barato.
- **Por qué no todo en plazo fijo**: históricamente, en Argentina, los instrumentos en pesos a tasa fija perdieron contra el dólar en los momentos de devaluación. Tener una parte en dólares protege el poder de compra.
- **Por qué ETFs y no acciones sueltas**: un ETF como SPY tiene 500 empresas; si una quiebra, casi no se nota. Elegir acciones sueltas requiere saber analizarlas, y la mayoría de los profesionales no le gana al índice.
- **Por qué poco en acciones argentinas**: tu sueldo, tu casa y tu vida ya dependen de la economía argentina. Diversificar afuera reduce el riesgo de que todo vaya mal al mismo tiempo.
- **Simple es mejor**: con 4 o 6 instrumentos alcanza. Más instrumentos no significa más diversificación si todos se mueven igual.

## Concentración: cuántos instrumentos por categoría

El script avisa si un solo bono o activo no diversificado pasa el 25 % de la cartera, o una sola acción el 10 %. Por eso:

- **Renta fija dólares** de 35–40 %: repartila en al menos dos instrumentos (por ejemplo un bono soberano y una ON, o dos ON) o usá un FCI de renta fija en dólares, que ya está diversificado. Así no dependés de un solo emisor.
- **Acciones internacionales**: un ETF amplio (SPY, VT) puede ser el 100 % de la categoría sin problema; ya trae cientos de empresas.
- **Acciones sueltas** (una empresa): si la persona quiere tenerlas, que sean una parte chica y cada una ≤ 10 %.

## Ajustes según la persona

- Horizonte corto u objetivo concreto (comprar un auto en 2 años): ir hacia el conservador, más liquidez y renta fija de corto plazo.
- Ahorra solo en pesos y no puede dolarizar: más peso a renta fija en pesos con cobertura de inflación (UVA/CER) y a CEDEARs, que siguen al dólar.
- Montos chicos: empezar con 2 o 3 instrumentos (por ejemplo un FCI money market, un CEDEAR de ETF amplio y un FCI de renta fija en dólares) y sumar categorías cuando crezca la cartera.

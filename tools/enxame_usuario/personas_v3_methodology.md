# Metodologia de Migração das Personas v1 -> v3.0

## Resumo
- Registros legados analisados: 300
- Personas nominais canônicas: 20
- Textos únicos legados: 21

## Anomalias Legadas
- `fernanda_costa` (Fernanda Costa) possui 2 variantes textuais.
  - Variante canônica: 12 ocorrências, IDs [17, 18, 19, 20, 117, 118, 119, 120, 217, 218, 219, 220]
  - Variante legada não canônica: 12 ocorrências, IDs [81, 82, 83, 84, 157, 158, 159, 160, 257, 258, 259, 260]

## Ajustes por Persona
- `ana_beatriz_silva` | peso=1.0 | duracao={'rapida': 0.99, 'media': 1.12, 'lenta': 0.85} | offset={'horario-comercial': 0.94, 'noite': 1.09} | weekend={'false': 0.83, 'true': 1.8} | Freelancer jovem com rotina mais flexível; leve viés para noite e fim de semana, mantendo duração média.
- `carla_mendes` | peso=1.0 | duracao={'rapida': 1.73, 'media': 0.64, 'lenta': 0.85} | offset={'horario-comercial': 1.06, 'noite': 0.91} | weekend={'false': 1.0, 'true': 1.02} | Gestora analítica com deficiência auditiva; prioriza atendimentos curtos e claros, majoritariamente em dias úteis.
- `carlos_ferreira` | peso=1.0 | duracao={'rapida': 1.73, 'media': 0.64, 'lenta': 0.85} | offset={'horario-comercial': 1.06, 'noite': 0.91} | weekend={'false': 1.08, 'true': 0.6} | Busca eficiência para resolver assuntos cotidianos; viés para duração rápida e baixa incidência de fim de semana.
- `miguel_santos` | peso=1.0 | duracao={'rapida': 0.6, 'media': 0.96, 'lenta': 1.7} | offset={'horario-comercial': 0.94, 'noite': 1.09} | weekend={'false': 1.08, 'true': 0.6} | Caso de acessibilidade técnica exige precisão e paciência; favorece interações lentas e em dias úteis.
- `fernanda_costa` | peso=2.0 | duracao={'rapida': 0.6, 'media': 1.16, 'lenta': 1.54} | offset={'horario-comercial': 0.82, 'noite': 1.27} | weekend={'false': 0.85, 'true': 1.8} | Caso de renegociação sensível e emocional; aumenta interações lentas e noturnas, com alguma presença em fim de semana.
- `ricardo_tanaka` | peso=1.0 | duracao={'rapida': 1.73, 'media': 0.64, 'lenta': 0.85} | offset={'horario-comercial': 1.18, 'noite': 0.73} | weekend={'false': 1.08, 'true': 0.6} | Executivo metódico e numérico; reforça horário comercial e respostas rápidas em contexto profissional.
- `antonia_silveira` | peso=2.0 | duracao={'rapida': 0.6, 'media': 0.98, 'lenta': 1.77} | offset={'horario-comercial': 0.95, 'noite': 1.08} | weekend={'false': 0.94, 'true': 1.37} | Perfil idoso, cauteloso e com desconfiança digital; favorece interações lentas e em horário comercial.
- `paulo_henrique_almeida` | peso=1.0 | duracao={'rapida': 1.73, 'media': 1.12, 'lenta': 0.6} | offset={'horario-comercial': 0.94, 'noite': 1.09} | weekend={'false': 0.91, 'true': 1.53} | Caso urgente e indignado; puxa para respostas rápidas e alguma incidência noturna.
- `camila_rocha` | peso=2.0 | duracao={'rapida': 1.78, 'media': 0.89, 'lenta': 0.6} | offset={'horario-comercial': 1.01, 'noite': 0.98} | weekend={'false': 1.03, 'true': 0.82} | Empresária objetiva e dinâmica; favorece conversas rápidas e úteis, com menor peso em fins de semana.
- `jose_carlos_da_silva` | peso=2.0 | duracao={'rapida': 0.6, 'media': 1.16, 'lenta': 1.42} | offset={'horario-comercial': 0.82, 'noite': 1.27} | weekend={'false': 0.89, 'true': 1.65} | Orçamento apertado e busca por explicações simples; favorece duração média/lenta e algum uso fora do horário comercial.
- `eduardo_martins` | peso=2.0 | duracao={'rapida': 1.51, 'media': 0.8, 'lenta': 0.83} | offset={'horario-comercial': 1.2, 'noite': 0.68} | weekend={'false': 1.12, 'true': 0.6} | Persona técnica e orientada a números; favorece respostas rápidas em contexto profissional.
- `gabriela_ferreira` | peso=1.0 | duracao={'rapida': 0.99, 'media': 1.12, 'lenta': 0.85} | offset={'horario-comercial': 1.06, 'noite': 0.91} | weekend={'false': 1.08, 'true': 0.6} | Profissional criativa com demanda prática; mantém viés moderado para horário comercial e dias úteis.
- `rafael_gomes` | peso=1.0 | duracao={'rapida': 1.48, 'media': 0.96, 'lenta': 0.64} | offset={'horario-comercial': 1.06, 'noite': 0.91} | weekend={'false': 0.75, 'true': 1.8} | Perfil entusiasmado e disperso; mistura respostas rápidas e médias, com maior elasticidade de fim de semana.
- `luisa_oliveira` | peso=1.0 | duracao={'rapida': 0.99, 'media': 1.12, 'lenta': 0.85} | offset={'horario-comercial': 0.82, 'noite': 1.27} | weekend={'false': 0.75, 'true': 1.8} | Estudante e estagiária em início de vida financeira; reforça noite/fim de semana com conversas geralmente médias.
- `marina_rodrigues` | peso=1.0 | duracao={'rapida': 1.73, 'media': 0.64, 'lenta': 0.85} | offset={'horario-comercial': 0.6, 'noite': 1.63} | weekend={'false': 0.66, 'true': 1.8} | Médica plantonista com agenda irregular; desloca interações para noite e fim de semana, com respostas rápidas.
- `daniela_nascimento` | peso=1.0 | duracao={'rapida': 0.99, 'media': 1.12, 'lenta': 0.85} | offset={'horario-comercial': 1.06, 'noite': 0.91} | weekend={'false': 1.08, 'true': 0.6} | Perfil organizado e documentado; distribuição moderada com predominância de dias úteis e horário comercial.
- `roberto_yamamoto` | peso=1.0 | duracao={'rapida': 0.74, 'media': 0.8, 'lenta': 1.49} | offset={'horario-comercial': 1.18, 'noite': 0.73} | weekend={'false': 1.08, 'true': 0.6} | Consultor processual e regulatório; favorece atendimentos mais longos e em dias úteis.
- `patricia_santana` | peso=1.0 | duracao={'rapida': 0.99, 'media': 1.12, 'lenta': 0.85} | offset={'horario-comercial': 1.18, 'noite': 0.73} | weekend={'false': 1.08, 'true': 0.6} | Advogada com atuação estruturada; mantém interações centradas em horário comercial e dias úteis.
- `joao_pedro_oliveira` | peso=1.0 | duracao={'rapida': 1.73, 'media': 1.12, 'lenta': 0.6} | offset={'horario-comercial': 0.82, 'noite': 1.27} | weekend={'false': 0.75, 'true': 1.8} | Estudante de tecnologia com rotina flexível; reforça noite e fim de semana, sem cenários lentos.
- `helena_mendonca` | peso=1.0 | duracao={'rapida': 0.6, 'media': 1.12, 'lenta': 1.49} | offset={'horario-comercial': 0.94, 'noite': 1.09} | weekend={'false': 0.91, 'true': 1.53} | Situação documental delicada e emocionalmente carregada; tende a conversas mais longas e cuidadosas.

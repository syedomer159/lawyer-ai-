# Eval report: analysis (cloud profile)

Deterministic scoring against samples/*/answer_key.yaml; see evals/analysis_suite.py.

| case | contradiction_recall | matched_share | effect_correct | gap_recall | adverse_recall | citation_verified | conflicts_predicted | issues | llm_calls | cost_usd | seconds |
|---|---|---|---|---|---|---|---|---|---|---|---|
| case1_state_v_arjun_verma | 0.857 | 0.625 | 1.0 | 1.0 | 0.5 | 1.0 | 16 | 12 | 35 | 0.0607 | 257.3 |
| case2_state_v_kavita_rao | 0.833 | 0.75 | 1.0 | 0.75 | 1.0 | 1.0 | 12 | 12 | 36 | 0.0576 | 317.9 |

## case1_state_v_arjun_verma: missed contradictions
- C1 time of incident

## case1_state_v_arjun_verma: missed gaps
- none

## case1_state_v_arjun_verma: predicted conflicts not in the key (review by hand)
- [high/helps] suspect clothing description: PW1 Sunita Sharma states the assailant wore a blue jacket, while PW2 Ramesh Kumar states the assailant wore a red jacket, creating a direct contradiction between key prosecution eye-witnesses regarding the suspect's clothing.
- [high/helps] recovery of stolen property and jacket: Ramesh Kumar (PW2) claims the perpetrator wore a red jacket [37], but the recovery memo prepared by SI Pradeep Rathore records the recovery of a blue jacket from the accused's almirah [69].
- [high/helps] recovery of stolen property and jacket: While the recovery memo records a blue jacket being recovered from the accused's almirah [69], client interview notes state that the blue jacket does not belong to Arjun and he only owns a black jacket [100, 101].
- [high/helps] identification of the accused: Informant Smt. Sunita Sharma claimed she could identify the assailant, but the identification of the accused in custody was instead conducted by Ramesh Kumar (PW-2) after the police showed the boy to him at the station.
- [medium/helps] suspect clothing description: PW1 Sunita Sharma specifically identifies the jacket as blue, while PW3 Mohd. Irfan states he could not tell the colour of the dark jacket.
- [low/helps] time and date of occurrence: PW2 Ramesh Kumar states the incident occurred at about 8:30 pm, whereas PW3 Mohd. Irfan states it was at around 9:00 pm, creating a discrepancy in the timeline of the occurrence.

## case2_state_v_kavita_rao: missed contradictions
- C5 eyewitness's distance from the spot

## case2_state_v_kavita_rao: missed gaps
- G4 FIR based on eyewitness information

## case2_state_v_kavita_rao: predicted conflicts not in the key (review by hand)
- [high/helps] actions of the driver after the accident: Witness Lata Pawar states that a man got out of the car and walked towards the railway station, which directly corroborates our client Kavita Rao's account that the driver Manoj Shinde panicked and fled towards the railway station.
- [high/hurts] actions of the driver after the accident: Witness Anil Deshmukh claims the woman driver got down from the car, whereas witness Lata Pawar claims a man got out and walked away while the lady stayed, creating a direct contradiction between prosecution witnesses regarding who exited the vehicle.
- [medium/helps] side of impact on the victim: Eyewitness Anil Deshmukh asserts the car struck the victim's left side, but the Motor Vehicle Inspection Report notes the vehicle damage (dent on the bonnet) was on the left side, conflicting with the eyewitness's account of how the pedestrian and car approached or faced each other.

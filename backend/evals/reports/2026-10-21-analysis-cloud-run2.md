# Eval report: analysis (cloud profile)

Deterministic scoring against samples/*/answer_key.yaml; see evals/analysis_suite.py.

| case | contradiction_recall | matched_share | effect_correct | gap_recall | adverse_recall | citation_verified | conflicts_predicted | issues | llm_calls | cost_usd | seconds |
|---|---|---|---|---|---|---|---|---|---|---|---|
| case1_state_v_arjun_verma | 1.0 | 0.769 | 1.0 | 0.833 | 1.0 | 1.0 | 13 | 12 | 34 | 0.0631 | 246.5 |
| case2_state_v_kavita_rao | 0.167 | 0.333 | 1.0 | 0.75 | 0.5 | 1.0 | 3 | 12 | 32 | 0.0575 | 255.2 |

## case1_state_v_arjun_verma: missed contradictions
- none

## case1_state_v_arjun_verma: missed gaps
- G1 Prompt FIR / explanation of delay

## case1_state_v_arjun_verma: predicted conflicts not in the key (review by hand)
- [high/helps] suspect clothing / jacket description and recovery: The police recovery memo records finding a blue jacket, whereas client interview notes state that Arjun Verma only owns a black jacket, creating a contradiction between the official recovery and the defence's factual stance.
- [high/helps] arrest details and date/location discrepancy: SI Pradeep Rathore records in the arrest memo that Arjun was arrested at the Navgarh bus stand (claim 62), while the defence notes state he was picked up directly from his house (claim 106), contradicting the official place of arrest.
- [high/helps] recovery memo and panch witness veracity: While the recovery memo suggests a formal search and recovery witnessed by panch witnesses, Suresh Yadav categorically states he never saw any chain being recovered.

## case2_state_v_kavita_rao: missed contradictions
- C2 colour of the vehicle
- C3 direction of crossing and side of impact
- C4 speed of the vehicle
- C5 eyewitness's distance from the spot
- C6 how and where the victim entered the road

## case2_state_v_kavita_rao: missed gaps
- G4 FIR based on eyewitness information

## case2_state_v_kavita_rao: predicted conflicts not in the key (review by hand)
- [medium/helps] actions of occupants after accident: PW1 Anil Deshmukh claims a woman got down from the car, whereas PW2 Lata Pawar claims a man got out of the car and walked away, creating a contradiction regarding which occupant exited the vehicle.
- [low/helps] parked bus at the scene: Lata Pawar (PW2) states a bus was parked at the bus stop, which is consistent with the defence notes stating the deceased pedestrian emerged from behind a parked MSRTC bus, corroborating our client's version that the pedestrian's appearance was sudden and obstructed.

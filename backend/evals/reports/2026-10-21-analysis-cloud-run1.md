# Eval report: analysis (cloud profile)

Deterministic scoring against samples/*/answer_key.yaml; see evals/analysis_suite.py.

| case | contradiction_recall | matched_share | effect_correct | gap_recall | adverse_recall | citation_verified | conflicts_predicted | issues | llm_calls | cost_usd | seconds |
|---|---|---|---|---|---|---|---|---|---|---|---|
| case1_state_v_arjun_verma | 0.857 | 0.636 | 1.0 | 0.833 | 0.5 | 1.0 | 11 | 12 | 34 | 0.1243 | 264.8 |
| case2_state_v_kavita_rao | 0.333 | 0.625 | 1.0 | 0.75 | 0.5 | 1.0 | 8 | 12 | 33 | 0.0602 | 244.5 |

## case1_state_v_arjun_verma: missed contradictions
- C1 time of incident

## case1_state_v_arjun_verma: missed gaps
- G1 Prompt FIR / explanation of delay

## case1_state_v_arjun_verma: predicted conflicts not in the key (review by hand)
- [medium/helps] time of incident: PW2 Ramesh Kumar stated that the incident occurred at about 8:30 pm, whereas complainant PW1 Sunita Sharma stated it occurred at about 9:15 pm, creating a 45-minute discrepancy between prosecution witnesses.
- [high/helps] time of incident: PW1 Sunita Sharma testified that the incident took place at about 9:15 pm, whereas the CCTV still from CAM-03 records the timestamp as 20:41:07 (8:41 pm).
- [high/helps] injuries to complainant: Sunita Sharma claims she fell and sustained a bleeding injury to her right elbow, while Dr. Meera Joshi recorded in the MLC opinion that there was no injury.
- [low/helps] age and build of suspect: Ramesh Kumar described the offender as thin, but Arjun Verma's arrest memo records his age and build differently, creating a slight discrepancy regarding the perpetrator's physical description.

## case2_state_v_kavita_rao: missed contradictions
- C2 colour of the vehicle
- C3 direction of crossing and side of impact
- C4 speed of the vehicle
- C5 eyewitness's distance from the spot

## case2_state_v_kavita_rao: missed gaps
- G4 FIR based on eyewitness information

## case2_state_v_kavita_rao: predicted conflicts not in the key (review by hand)
- [low/helps] time of incident: PW2 Lata Pawar states the time was about 7:00 am, whereas the FIR records the incident at 07:10 hrs, creating a timing discrepancy that helps question the exact timeline of events.
- [high/helps] collision and vehicle speed: Nitin Patil states the crowd told him a white SUV was involved, whereas eyewitness Anil Deshmukh claims the vehicle was a silver-grey car, creating a contradiction regarding the car's color and type.
- [medium/helps] actions after accident: PW1 Anil Deshmukh claims the woman got down from the car, whereas PW2 Lata Pawar claims that the man got out and walked away while the woman stayed, contradicting who exited the vehicle immediately after the accident.

package forge.legal

default allow := false

deny_legal_advice contains msg if {
  input.action_type == "email_send"
  regex.match("(?i)you should (sue|file)|I recommend (filing|suing)", input.content)
  msg := "Contains direct legal advice - licensed attorney required"
}

deny_conflict contains msg if {
  some entity in input.entities
  some known in data.conflicts.known
  lower(entity) == lower(known)
  msg := sprintf("Conflict of interest detected: %s", [entity])
}

violations contains v if {
  v := deny_legal_advice[_]
}

violations contains v if {
  v := deny_conflict[_]
}

allow if {
  count(violations) == 0
}

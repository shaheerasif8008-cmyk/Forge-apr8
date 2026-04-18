package forge.healthcare

default allow := false

deny_phi contains msg if {
  regex.match("(?i)patient|diagnosis|dob|ssn|medical record", input.content)
  not input.scrubbed
  msg := "Potential PHI detected - scrub or redact before delivery"
}

violations := [v | v := deny_phi[_]]
allow := count(violations) == 0

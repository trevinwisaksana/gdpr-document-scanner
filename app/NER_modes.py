NER_MODES = {
    "gdpr_minimal":[        # Minimal gdpr mode
        "Person",
        "EmailAddress",
        "PhoneNumber",
        "IpAddress",
        "PersonalData",
        "SensitiveData"
    ],
    "gdpr_full": [          # in depth gdpr mode
        "DataController",
        "DataProcessor",
        "PersonalData",
        "SensitiveData",
        "LegalBasis",
        "RetentionPeriod",
        "DataSubjectRights",
        "DataBreach",
        "ThirdCountryTransfer",
        "SecurityMeasure",
        "Person",
        "EmailAddress",
        "PhoneNumber",
        "IpAddress"
    ]
}
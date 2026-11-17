const companyFileInput =
    document.getElementById("companyFile");

const bankFileInput =
    document.getElementById("bankFile");


companyFileInput.addEventListener(
    "change",
    function () {

        document.getElementById(
            "companyFileName"
        ).textContent =
            this.files.length > 0
                ? this.files[0].name
                : "No file selected";

    }
);


bankFileInput.addEventListener(
    "change",
    function () {

        document.getElementById(
            "bankFileName"
        ).textContent =
            this.files.length > 0
                ? this.files[0].name
                : "No file selected";

    }
);


async function runReconciliation() {

    const companyFile =
        companyFileInput.files[0];

    const bankFile =
        bankFileInput.files[0];


    const errorMessage =
        document.getElementById(
            "errorMessage"
        );

    const loading =
        document.getElementById(
            "loading"
        );

    const button =
        document.getElementById(
            "reconcileBtn"
        );


    errorMessage.classList.add(
        "hidden"
    );


    if (!companyFile || !bankFile) {

        errorMessage.textContent =
            "Please upload both Company and Bank transaction files.";

        errorMessage.classList.remove(
            "hidden"
        );

        return;
    }


    const formData =
        new FormData();


    formData.append(
        "company_file",
        companyFile
    );


    formData.append(
        "bank_file",
        bankFile
    );


    loading.classList.remove(
        "hidden"
    );


    button.disabled = true;

    document.getElementById(
        "buttonText"
    ).textContent =
        "Analyzing Transactions...";


    try {

        const response = await fetch(
    "https://ai-finance-controller-gules.vercel.app/reconcile",
    {
        method: "POST",
        body: formData
    }
);

        if (!response.ok) {

            throw new Error(
                "Failed to process transactions."
            );

        }


        const data =
            await response.json();


        updateDashboard(data);

        displayResults(data.results);


        document.getElementById(
            "results"
        ).scrollIntoView({
            behavior: "smooth"
        });


    }

    catch (error) {

        errorMessage.textContent =
            "Error: " + error.message;

        errorMessage.classList.remove(
            "hidden"
        );

    }

    finally {

        loading.classList.add(
            "hidden"
        );

        button.disabled = false;

        document.getElementById(
            "buttonText"
        ).textContent =
            "✦ Run AI Reconciliation";

    }

}


function updateDashboard(data) {

    const summary =
        data.summary;


    document.getElementById(
        "totalTransactions"
    ).textContent =
        summary.total_company_transactions;


    document.getElementById(
        "matched"
    ).textContent =
        summary.matched;


    document.getElementById(
        "possibleMatches"
    ).textContent =
        summary.possible_matches;


    document.getElementById(
        "unmatched"
    ).textContent =
        summary.unmatched;


    document.getElementById(
        "matchRate"
    ).textContent =
        "Match Rate: " +
        summary.match_rate +
        "%";

}


function displayResults(results) {

    const resultsBody =
        document.getElementById(
            "resultsBody"
        );


    resultsBody.innerHTML = "";


    results.forEach(
        function (result) {

            let statusClass;


            if (
                result.status === "MATCHED"
            ) {

                statusClass =
                    "status-matched";

            }

            else if (
                result.status ===
                "POSSIBLE MATCH"
            ) {

                statusClass =
                    "status-possible";

            }

            else {

                statusClass =
                    "status-unmatched";

            }


            const confidence =
                Math.round(
                    result.confidence * 100
                );


            const row =
                document.createElement("tr");


            row.innerHTML = `

                <td>
                    <strong>
                        ${result.company_transaction_id}
                    </strong>
                </td>

                <td>
                    ${
                        result.bank_transaction_id
                        || "—"
                    }
                </td>

                <td>

                    <span
                        class="
                        status-badge
                        ${statusClass}
                        "
                    >

                        ${result.status}

                    </span>

                </td>

                <td class="confidence">

                    ${confidence}%

                </td>

            `;


            resultsBody.appendChild(
                row
            );

        }
    );

}

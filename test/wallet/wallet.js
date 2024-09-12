const scanButton = document.getElementById('scan-button');
const walletGrid = document.getElementById('wallet-grid');
const readerDiv = document.getElementById('reader');
const questionScreen = document.getElementById('question-screen');
const shareQuestion = document.getElementById('share-question');
const yesButton = document.getElementById('yes-button');
const noButton = document.getElementById('no-button');

let credentials = [];

function loadCredentials() {
  const storedCredentials = localStorage.getItem('credentials');
  if (storedCredentials) {
    credentials = JSON.parse(storedCredentials);
  }
}

function saveCredentials() {
  localStorage.setItem('credentials', JSON.stringify(credentials));
}

function displayCredentials() {
  walletGrid.innerHTML = '';
  credentials.forEach((cred) => {
    if (!cred.isShareAction) { // Alleen normale kaartjes tonen, geen deelacties
      const card = document.createElement('div');
      card.className = 'card';
      card.innerHTML = `<h3>${cred.name}</h3><p>Valid until ${cred.validUntil}</p>`;
      walletGrid.appendChild(card);
    }
  });
}

scanButton.addEventListener('click', () => {
  readerDiv.style.display = 'block';
  const html5QrCode = new Html5Qrcode("reader");

  html5QrCode.start(
    { facingMode: "environment" },
    { fps: 10, qrbox: 250 },
    (decodedText) => {
      try {
        const data = JSON.parse(decodedText);

        // If the QR-code is from a verifier, ask to share specific card
        if (data.verifier) {
          const requestedCard = data.requestedCard;
          const requester = data.requester;

          // Stop the QR scanner when the question screen is shown
          html5QrCode.stop().then(() => {
            readerDiv.style.display = 'none'; // Verberg de QR-scanner
          });

          // Toon vraag in full screen
          questionScreen.style.display = 'block';
          shareQuestion.innerText = `Wil je het kaartje "${requestedCard}" delen met ${requester}?`;

          // Handle Yes/No response
          yesButton.onclick = () => {
            // Sla de deelactie op in localStorage zonder deze als kaartje te tonen
            const timestamp = new Date().toLocaleString();
            credentials.push({
              name: `Kaartje "${requestedCard}" gedeeld met ${requester}`,
              validUntil: timestamp,
              isShareAction: true // Markeer als deelactie
            });
            saveCredentials();
            questionScreen.style.display = 'none'; // Ga terug naar het hoofscherm zonder de actie te tonen
          };

          noButton.onclick = () => {
            questionScreen.style.display = 'none'; // Ga terug naar het hoofscherm
          };

        } else {
          // Verwerk issuer-QR-code (normaal kaartje opslaan)
          credentials.push({ name: data.name || "Unknown", validUntil: 'N/A', data: data });
          saveCredentials();
          displayCredentials();
        }

      } catch (error) {
        console.error(`QR-code parse error: ${error}`);
      }
    },
    (errorMessage) => {
      console.error(`QR scan failed: ${errorMessage}`);
    }
  );
});

loadCredentials();
displayCredentials();

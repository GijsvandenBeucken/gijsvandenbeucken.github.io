/***********************************************
 * assessment.js
 ***********************************************/
/** 1) CODEBLOK "ECHTE VRAGEN" (nu ingevuld)
 *    Hier vullen we alle subthema's en hun vragen (zo volledig als in je eerdere overzicht).
 */
const QUESTIONS = {
  // ============== STRATEGIE ==============
  "Strategie - Governance": [
    "De organisatiestructuur van de governance is goed beschreven en onderbouwd.",
    "De besluitvormingsprocessen van de governance zijn beschreven waarbij het helder is welk gremium over welke onderwerpen gaat.",
    "Het is duidelijk wie de belanghebbenden zijn en hoe de belanghebbenden mee kunnen doen bij de besturing van een standaard en/of stelsel.",
    "Het is duidelijk waar welke stakeholders aan moeten participeren en welke rol zij dienen te vervullen.",
    "Er is een procedure aanwezig voor het laten deelnemen van organisaties aan de governance.",
    "Er is transparante besturing op strategisch niveau ingericht die passend is voor de ambities van de standaard of het stelsel.",
    "Er is transparante besturing op tactisch niveau ingericht die passend is voor de ambities van de standaard of het stelsel.",
    "Er is transparante besturing op operationeel niveau ingericht die passend is voor de ambities van de standaard of het stelsel.",
    "De escalatieprocedures en lijnen zijn aanwezig en ze zijn goed beschreven.",
    "De governance kan een werkgroep instellen. Het is duidelijk beschreven hoe de opdracht tot stand komt en hoe hierover wordt gerapporteerd.",
    "De doelstellingen, resultaten en werkafspraken zijn vastgelegd en door de stakeholders ondertekend/bekrachtigd.",
    "Er is een stakeholder-analyse gemaakt en vastgelegd. Deze analyse wordt periodiek herhaald om goed in te spelen op ontwikkelingen in de omgeving.",
    // Nieuwe vragen voor governance
    "Er is een expliciete governance structuur voor publiek-private samenwerking vastgelegd.",
    "De verantwoordelijkheden tussen publieke en private partijen zijn duidelijk gedefinieerd en gedocumenteerd.",
    "Er zijn effectieve besluitvormingsprocessen ingericht voor publiek-private samenwerking.",
    "Het is duidelijk hoe private partijen kunnen participeren in de governance structuur."
  ],

  "Strategie - Visie": [
    "Er is een duidelijk geëxpliciteerde visie over de bovenliggende doelstellingen van de standaard of stelsel beschikbaar.",
    "De visie wordt actief gedeeld met de omgeving.",
    "Een meerjarenplanning waarbij de visie is vertaald in activiteiten is publiek beschikbaar.",
    // Nieuwe vragen voor coherent dienstverleningslandschap
    "Er is een duidelijke visie op de integratie van bestaande en nieuwe diensten.",
    "Het is helder hoe verschillende diensten samen een coherent landschap vormen.",
    "Er zijn concrete doelstellingen voor het realiseren van een gebruiksvriendelijk dienstverleningslandschap."
  ],

  "Strategie - Business Case": [
    "Er is goed inzicht in de te bereiken voordelen die de standaard of het stelsel kan opleveren met de daarvoor benodigde inspanning en kosten.",
    "De business case wordt periodiek herijkt.",
    "Er wordt concreet gestuurd op het realiseren van waarde van het stelsel of standaard."
  ],

  "Strategie - Financiën": [
    "De structurele financiering is voor de komende 2 tot 3 jaar geregeld.",
    "De financiering is gebaseerd op een grondige behoefte analyse voor het beheren en doorontwikkelen van het stelsel of standaard."
  ],

  "Strategie - Toezicht": [
    "Er is een onafhankelijke toezichthoudende partij aangewezen die zorg draagt voor het toetsen op het naleven van de binnen het stelsel overeengekomen afspraken.",
    "De toezichthouder heeft voldoende instrumenten en mandaat rond het uitvoeren van toezichttaken en de naleving van de eisen door de deelnemers."
  ],

  // ============== TACTIEK ==============
  "Tactiek - Community": [
    "De ambities, doelstellingen en activiteiten van de community zijn formeel vastgelegd.",
    "De rollen en verantwoordelijkheden binnen de community zijn gedefinieerd en ingeregeld. De 'eigenaar' van de community is bekend en er is ondersteuning voor de community georganiseerd.",
    "Het is duidelijk wie de leden zijn van de community en welke rol deze leden vervullen.",
    // Nieuwe vragen voor onderzoek
    "Er is een duidelijke structuur voor gezamenlijk onderzoek tussen stakeholders.",
    "Onderzoeksagenda's worden gezamenlijk bepaald door publieke en private partijen.",
    "Er zijn heldere afspraken over het delen van onderzoeksresultaten."
  ],

  "Tactiek - Adoptie en Erkenning": [
    "Er bestaat een adoptiestrategie waarmee het draagvlak van het stelsel of standaard wordt bevorderd.",
    "De adoptiestrategie bevat ook pilots om meerwaarde aan de verschillende stakeholders te laten zien.",
    "Er is een analyse gemaakt van de in te zetten adoptie-instrumenten. De relevante instrumenten zijn uitgewerkt en zijn ingezet.",
    "Een referentie-implementatie is onderdeel van de adoptiestrategie om de verschillende stakeholders te overtuigen van de meerwaarde van het stelsel.",
    "De doelen waarmee de 'markt' verleid gaat worden gebruik te maken van het stelsel zijn expliciet beschreven.",
    // Nieuwe vragen voor coherent dienstverleningslandschap
    "Er is een duidelijke strategie voor het integreren van nieuwe diensten in bestaande dienstverleningspatronen.",
    "Er wordt actief gestuurd op gebruikerservaring over verschillende diensten heen.",
    "Er zijn concrete plannen voor het harmoniseren van verschillende dienstverleningspatronen."
  ],

  "Tactiek - Architectuur": [
    "De architectuur van het stelsel of standaard is volledig beschreven.",
    "De relatie en afhankelijkheden met andere stelsels en/of standaarden zijn volledig in kaart gebracht.",
    "Er vindt afstemming plaats met overige stelsels en standaarden daar waar sprake is van raakvlak en/of overlap.",
    "Er wordt vanuit het stelsel of standaard actief deelgenomen aan internationale gremia. Relevante internationale ontwikkelingen worden gemonitord.",
    // Nieuwe vragen voor publiek-private stelselontwikkeling
    "Er is een duidelijke architectuurvisie voor de integratie van publieke en private diensten.",
    "De architectuur faciliteert flexibele aansluiting van zowel publieke als private partijen.",
    "Er zijn duidelijke standaarden en richtlijnen voor de ontwikkeling van publiek-private diensten."
  ],

  "Tactiek - Roadmapping": [
    "Er is een ontwikkelagenda opgesteld waarmee invulling wordt gegeven aan de geformuleerde visie. Deze agenda maakt duidelijk welke ontwikkeling op welk moment in de tijd gerealiseerd gaat worden."
  ],

  "Tactiek - Risicoanalyse": [
    "Er wordt jaarlijks een stelselrisicoanalyse uitgevoerd met de deelnemers binnen het stelsel.",
    "Er bestaat een kader met normen rond informatiebeveiliging in het afsprakenstelsel die van toepassing is op de geleverde diensten door de deelnemers.",
    "De resultaten van de stelselrisicoanalyse maken onderdeel uit van een 'plan do check act'-cyclus. De resultaten worden gedeeld met de governance."
  ],

  // ============== OPERATIONEEL ==============
  "Operationeel - Wensen en eisen": [
    "Er is een wijzigingsprocedure ingeregeld en gepubliceerd.",
    "Er is een publiek toegankelijk platform beschikbaar waarbij wijzigingsvoorstellen kunnen worden ingediend en waarvan de afhandeling kan worden gemonitord."
  ],

  "Operationeel - Ontwikkeling": [
    "Wijzigingen worden eerst conceptueel getoetst voordat ze technisch worden geïmplementeerd.",
    "De architectuur van het stelsel of standaard is in detail beschreven. Duidelijk is wat de van toepassing zijnde kaders zijn en welke modules onderscheiden worden.",
    // Nieuwe vragen voor publiek-private stelselontwikkeling
    "Er is een gestructureerd proces voor de gezamenlijke ontwikkeling van publiek-private oplossingen.",
    "Technische specificaties worden in co-creatie tussen publieke en private partijen ontwikkeld."
  ],

  "Operationeel - Uitvoering": [
    "Een aanpassing wordt eerst zorgvuldig ontworpen en getoetst voordat deze definitief wordt ingevoerd."
  ],

  "Operationeel - Documentatie": [
    "De specificaties van het stelsel of de standaard zijn beschikbaar en publiek toegankelijk.",
    "Alle relevante documenten voor de werking van het stelsel of de standaard zijn publiek toegankelijk.",
    "Het beheerproces is gedocumenteerd en publiek toegankelijk."
  ],

  // ============== IMPLEMENTATIE ONDERSTEUNING ==============
  "Implementatie Ondersteuning - Helpdesk": [
    "Er is een helpdesk beschikbaar waar vragen gesteld of verstoringen gemeld kunnen worden. Er is hulp georganiseerd voor zowel de gebruikers als voor de leveranciers.",
    "Er gelden concrete afspraken tussen de deelnemers over de te leveren beschikbaarheid en prestaties van diensten rond de helpdesk."
  ],

  "Implementatie Ondersteuning - Module Ontwikkeling": [
    "Er is een technisch adoptiebeleid voor de standaard of stelsel opgesteld.",
    "De standaard (of het stelsel) is in staat om verschillende stakeholders goed te bedienen met modules en libraries."
  ],

  "Implementatie Ondersteuning - Pilot/vernieuwing": [
    "De standaard of het stelsel heeft capaciteit om te innoveren.",
    "Het proces voor vernieuwing met de bijhorende beoordelingscriteria is beschreven.",
    // Nieuwe vragen voor beproevingen en uitkomsten
    "Er is een gestructureerde aanpak voor het uitvoeren van gezamenlijke pilots.",
    "Resultaten van beproevingen worden systematisch gedeeld met alle stakeholders.",
    "Er zijn duidelijke criteria voor het evalueren van pilot resultaten.",
    "Er is een helder proces voor het opschalen van succesvolle pilots."
  ],

  "Implementatie Ondersteuning - Validatie en Certificatie": [
    "Een validatieservice is aanwezig.",
    "Inspecties en/of toetsingen rond conformiteit van de standaard of stelsel zijn ingeregeld."
  ],

  // ============== COMMUNICATIE ==============
  "Communicatie - Promotie": [
    "Er bestaat een afgestemd communicatieplan voor de verschillende doelgroepen en wordt uitgevoerd.",
    "Het nut/noodzaak/voordeel van het stelsel of standaard wordt actief uitgedragen.",
    "Er is een duidelijk en toegankelijke uitleg van wat de diensten van een stelsel zijn en wat die concreet voor de gebruikers betekenen."
  ],

  "Communicatie - Publicatie": [
    "Er worden meerdere kanalen en platforms ingezet voor de communicatie naar diverse doelgroepen."
  ],

  "Communicatie - Klachtenafhandeling": [
    "Er bestaat een procedure wie klachten kan indienen over de standaard of het stelsel en waar die ingediend kunnen worden en hoe deze behandeld worden."
  ]
};


/** 2) CODEBLOK "DUMMY-ADVIEZEN" (uitgebreid):
 *   We kennen voor sommige subthema's concrete teksten (zie Strategy/Governance enz.),
 *   en voor alle overige 4 labels "moet nog gevuld worden".
 */
const DUMMY_ADVICE = {

  // ============== STRATEGIE ==============
  "Strategie - Governance": {
    "voldoet volledig":        "moet nog gevuld worden",
    "voldoet deels":           "moet nog gevuld worden",
    "ruimte voor verbetering": "moet nog gevuld worden",
    "voldoet onvoldoende":
      "De scores lijken aan te geven dat de governance nog niet op alle vlakken goed is ingeregeld en dat biedt ook kansen voor verbetering. Met welke onderdelen kan komend jaar winst worden behaald? Hoe ziet de veranderbehoefte er uit?"
  },

  "Strategie - Visie": {
    "voldoet volledig":        "moet nog gevuld worden",
    "voldoet deels":
      "De eerste stappen rond de visie lijken aan de hand van de scores gezet. Welke activiteiten kunnen hierbij nog helpen?",
    "ruimte voor verbetering": "moet nog gevuld worden",
    "voldoet onvoldoende":     "moet nog gevuld worden"
  },

  "Strategie - Business Case": {
    "voldoet volledig":        "moet nog gevuld worden",
    "voldoet deels":           "moet nog gevuld worden",
    "ruimte voor verbetering": "moet nog gevuld worden",
    "voldoet onvoldoende":
      "Het hebben van een goede businesscase is van belang voor het succes van een standaard of stelsel. Het helpt in grote mate in de investeringsbereidheid. Daarnaast wordt de businesscase ook gebruikt om het beleid op af te stemmen. Wat staat er op dit moment in de weg om tot een goede businesscase en het gebruik hiervan te komen?"
  },

  "Strategie - Financiën": {
    "voldoet volledig":        "moet nog gevuld worden",
    "voldoet deels":           "moet nog gevuld worden",
    "ruimte voor verbetering": "moet nog gevuld worden",
    "voldoet onvoldoende":
      "Een financieel model voor de lange termijn dat de benodigde opbrengsten garandeert is het voornaamste doel. Een standaard of stelsel ontwikkelen en beheren kost structureel geld en de dynamiek verschilt per context. Als het financieel model onvoldoende volwassen is, gaat veel energie naar de continuïteit. Is er volgend jaar wel budget? Dit belemmert de inzet en adoptie."
  },

  "Strategie - Toezicht": {
    "voldoet volledig":        "moet nog gevuld worden",
    "voldoet deels":           "moet nog gevuld worden",
    "ruimte voor verbetering": "moet nog gevuld worden",
    "voldoet onvoldoende":     "moet nog gevuld worden"
  },

  // ============== TACTIEK ==============
  "Tactiek - Community": {
    "voldoet volledig":        "moet nog gevuld worden",
    "voldoet deels":           "moet nog gevuld worden",
    "ruimte voor verbetering": "moet nog gevuld worden",
    "voldoet onvoldoende":     "moet nog gevuld worden"
  },

  "Tactiek - Adoptie en Erkenning": {
    "voldoet volledig":        "moet nog gevuld worden",
    "voldoet deels":           "moet nog gevuld worden",
    "ruimte voor verbetering": "moet nog gevuld worden",
    "voldoet onvoldoende":     "moet nog gevuld worden"
  },

  "Tactiek - Architectuur": {
    "voldoet volledig":        "moet nog gevuld worden",
    "voldoet deels":           "moet nog gevuld worden",
    "ruimte voor verbetering": "moet nog gevuld worden",
    "voldoet onvoldoende":     "moet nog gevuld worden"
  },

  "Tactiek - Roadmapping": {
    "voldoet volledig":        "moet nog gevuld worden",
    "voldoet deels":           "moet nog gevuld worden",
    "ruimte voor verbetering": "moet nog gevuld worden",
    "voldoet onvoldoende":     "moet nog gevuld worden"
  },

  "Tactiek - Risicoanalyse": {
    "voldoet volledig":        "moet nog gevuld worden",
    "voldoet deels":           "moet nog gevuld worden",
    "ruimte voor verbetering": "moet nog gevuld worden",
    "voldoet onvoldoende":     "moet nog gevuld worden"
  },

  // ============== OPERATIONEEL ==============
  "Operationeel - Wensen en eisen": {
    "voldoet volledig":        "moet nog gevuld worden",
    "voldoet deels":           "moet nog gevuld worden",
    "ruimte voor verbetering": "moet nog gevuld worden",
    "voldoet onvoldoende":     "moet nog gevuld worden"
  },

  "Operationeel - Ontwikkeling": {
    "voldoet volledig":        "moet nog gevuld worden",
    "voldoet deels":           "moet nog gevuld worden",
    "ruimte voor verbetering": "moet nog gevuld worden",
    "voldoet onvoldoende":     "moet nog gevuld worden"
  },

  "Operationeel - Uitvoering": {
    "voldoet volledig":        "moet nog gevuld worden",
    "voldoet deels":           "moet nog gevuld worden",
    "ruimte voor verbetering": "moet nog gevuld worden",
    "voldoet onvoldoende":     "moet nog gevuld worden"
  },

  "Operationeel - Documentatie": {
    "voldoet volledig":        "moet nog gevuld worden",
    "voldoet deels":           "moet nog gevuld worden",
    "ruimte voor verbetering": "moet nog gevuld worden",
    "voldoet onvoldoende":     "moet nog gevuld worden"
  },

  // ============== IMPLEMENTATIE ONDERSTEUNING ==============
  "Implementatie Ondersteuning - Helpdesk": {
    "voldoet volledig":        "moet nog gevuld worden",
    "voldoet deels":           "moet nog gevuld worden",
    "ruimte voor verbetering": "moet nog gevuld worden",
    "voldoet onvoldoende":     "moet nog gevuld worden"
  },

  "Implementatie Ondersteuning - Module Ontwikkeling": {
    "voldoet volledig":        "moet nog gevuld worden",
    "voldoet deels":           "moet nog gevuld worden",
    "ruimte voor verbetering": "moet nog gevuld worden",
    "voldoet onvoldoende":     "moet nog gevuld worden"
  },

  "Implementatie Ondersteuning - Pilot/vernieuwing": {
    "voldoet volledig":        "moet nog gevuld worden",
    "voldoet deels":           "moet nog gevuld worden",
    "ruimte voor verbetering": "moet nog gevuld worden",
    "voldoet onvoldoende":     "moet nog gevuld worden"
  },

  "Implementatie Ondersteuning - Validatie en Certificatie": {
    "voldoet volledig":        "moet nog gevuld worden",
    "voldoet deels":           "moet nog gevuld worden",
    "ruimte voor verbetering": "moet nog gevuld worden",
    "voldoet onvoldoende":     "moet nog gevuld worden"
  },

  // ============== COMMUNICATIE ==============
  "Communicatie - Promotie": {
    "voldoet volledig":        "moet nog gevuld worden",
    "voldoet deels":           "moet nog gevuld worden",
    "ruimte voor verbetering": "moet nog gevuld worden",
    "voldoet onvoldoende":     "moet nog gevuld worden"
  },

  "Communicatie - Publicatie": {
    "voldoet volledig":        "moet nog gevuld worden",
    "voldoet deels":           "moet nog gevuld worden",
    "ruimte voor verbetering": "moet nog gevuld worden",
    "voldoet onvoldoende":     "moet nog gevuld worden"
  },

  "Communicatie - Klachtenafhandeling": {
    "voldoet volledig":        "moet nog gevuld worden",
    "voldoet deels":           "moet nog gevuld worden",
    "ruimte voor verbetering": "moet nog gevuld worden",
    "voldoet onvoldoende":     "moet nog gevuld worden"
  }

};


/** 3) Lijst met subthema's en de ID's van de container in de HTML */
const SUBTHEMA_IDS = {
  "Strategie - Governance":             "subGovernance",
  "Strategie - Visie":                  "subVisie",
  "Strategie - Business Case":          "subBusCase",
  "Strategie - Financiën":             "subFinancien",
  "Strategie - Toezicht":              "subToezicht",

  "Tactiek - Community":                "subCommunity",
  "Tactiek - Adoptie en Erkenning":     "subAdoptie",
  "Tactiek - Architectuur":             "subArchitectuur",
  "Tactiek - Roadmapping":              "subRoadmapping",
  "Tactiek - Risicoanalyse":            "subRisicoanalyse",

  "Operationeel - Wensen en eisen":     "subWensenEisen",
  "Operationeel - Ontwikkeling":        "subOntwikkeling",
  "Operationeel - Uitvoering":          "subUitvoering",
  "Operationeel - Documentatie":        "subDocumentatie",

  "Implementatie Ondersteuning - Helpdesk": "subHelpdesk",
  "Implementatie Ondersteuning - Module Ontwikkeling": "subModuleOntwikkeling",
  "Implementatie Ondersteuning - Pilot/vernieuwing":   "subPilotVernieuwing",
  "Implementatie Ondersteuning - Validatie en Certificatie": "subValidatieCertificatie",

  "Communicatie - Promotie":           "subPromotie",
  "Communicatie - Publicatie":         "subPublicatie",
  "Communicatie - Klachtenafhandeling":"subKlachtenafhandeling"
};


/** 4) De dropdown-opties (scores), zonder in HTML elke keer te herhalen. */
const ANSWER_OPTIONS = [
  { value: "",  label: "--- kies ---" },
  { value: "5", label: "Helemaal mee eens" },
  { value: "4", label: "Eens" },
  { value: "3", label: "Neutraal" },
  { value: "1", label: "Oneens" },
  { value: "0", label: "Helemaal mee oneens" }
];

/** 5) Bij DOMContentLoaded: initialiseer alle subthema's in de HTML. */
document.addEventListener("DOMContentLoaded", initBomosAssessment);

function initBomosAssessment() {
  // Doorloop SUBTHEMA_IDS, check of er vragen bestaan in QUESTIONS, en vul de HTML
  for (let subName in SUBTHEMA_IDS) {
    const containerId = SUBTHEMA_IDS[subName];
    const containerEl = document.getElementById(containerId);
    if (!containerEl) continue;

    // Haal de vraag-array op (als die niet bestaat -> maak lege array)
    const qArr = QUESTIONS[subName] || [];

    qArr.forEach((qText, idx) => {
      // Voorzie een .question-block class (zodat we styling in CSS kunnen doen)
      let divQ = document.createElement("div");
      divQ.classList.add("question-block"); 
      
      // Zet de vraag in een <p> in plaats van in de <label>
      let p = document.createElement("p");
      p.innerText = (idx + 1) + ". " + qText;
      divQ.appendChild(p);

      // Maak de <select> (dropdown) eronder
      let sel = document.createElement("select");
      sel.dataset.subthema = subName;
      sel.dataset.qindex = idx;

      ANSWER_OPTIONS.forEach(opt => {
        let optEl = document.createElement("option");
        optEl.value = opt.value;
        optEl.textContent = opt.label;
        sel.appendChild(optEl);
      });

      divQ.appendChild(sel);
      containerEl.appendChild(divQ);
    });
  }
}


/** 6) Functies om door te klikken naar de volgende of vorige "thema-container" of naar het resultaten‑gedeelte. */
function gotoNextThema(currentId, nextId) {
  // Verwijder de 'active' class van het huidige scherm
  document.getElementById(currentId).classList.remove("active");
  
  // Als we naar het resultaten‑gedeelte gaan...
  if (nextId === "results") {
    // Zorg dat het resultaten‑gedeelte zichtbaar wordt
    document.getElementById("results").style.display = "block";
  } else {
    // Anders: zorg dat het resultaten‑gedeelte verborgen is en activeer het volgende thema
    document.getElementById("results").style.display = "none";
    document.getElementById(nextId).classList.add("active");
  }
}

function gotoPrevThema(currentId, prevId) {
  // Verwijder de 'active' class van het huidige scherm
  document.getElementById(currentId).classList.remove("active");
  // Zorg dat het resultaten‑gedeelte verborgen is
  document.getElementById("results").style.display = "none";
  // Activeer het vorige thema
  document.getElementById(prevId).classList.add("active");
}

function goBackFromResults() {
  // Verberg het resultaten‑gedeelte
  document.getElementById("results").style.display = "none";
  // Verwijder de 'active' class van alle thema-containers (optioneel voor consistentie)
  const themaContainers = document.querySelectorAll(".thema-container");
  themaContainers.forEach(el => el.classList.remove("active"));
  // Activeer het communicatie‑scherm zodat je daar terugkomt
  document.getElementById("thema-communicatie").classList.add("active");
}


/** 7) showResults: bereken per subthema score, categorie, etc. en toon in een TABEL. */
function showResults() {
  // 1) Lopen door SUBTHEMA_IDS en voor elk subName de selects uitlezen
  const resultsArr = [];  // We stoppen { subName, sum, count, pct, label, advice } etc. in array

  for (let subName in SUBTHEMA_IDS) {
    const containerId = SUBTHEMA_IDS[subName];
    const containerEl = document.getElementById(containerId);
    if (!containerEl) continue;

    const selList = containerEl.querySelectorAll("select");
    let totalScore = 0;
    let qCount = 0;

    selList.forEach(sel => {
      const val = parseInt(sel.value, 10);
      if (!isNaN(val)) {
        totalScore += val;
        qCount++;
      }
    });

    if (qCount === 0) {
      // Geen vragen? Sla over of reken 0% 
      continue;
    }

    const maxScore = qCount * 5;
    let pct = Math.round((totalScore / maxScore) * 100);

    // 2) Bepaal de label (4 categorieën)
    let label = "";
    if (pct >= 80) {
      label = "voldoet volledig";
    } else if (pct >= 60) {
      label = "voldoet deels";
    } else if (pct >= 40) {
      label = "ruimte voor verbetering";
    } else {
      label = "voldoet onvoldoende";
    }

    // 3) Haal een adviestekst (momenteel leeg) op
    let adviceText = getSubthemaAdvice(subName, label);

    // 4) resultsArr push
    resultsArr.push({
      subName,
      total: totalScore,
      count: qCount,
      max: maxScore,
      pct,
      label,
      advice: adviceText
    });
  }

  // 5) Toon in HTML-tabel
  createResultsTable(resultsArr);

  // 6) Laat #results zien
  document.getElementById("results").style.display = "block";
}


/** 
 * Ophalen advietekst. 
 */
function getSubthemaAdvice(subName, label) {
  if (DUMMY_ADVICE[subName] && DUMMY_ADVICE[subName][label]) {
    return DUMMY_ADVICE[subName][label];
  } else {
    // Anders de fallback-tekst
    return "Nog geen advies gedefinieerd voor: " + subName + " / " + label;
  }
}


/** 
 * 7) Kleur-codes op basis van label 
 */
function labelToColor(label) {
  switch(label) {
    case "voldoet volledig":        return "#9ADE7B"; // groen
    case "voldoet deels":           return "#EEF296"; // geel
    case "ruimte voor verbetering": return "#FFC78F"; // oranje
    case "voldoet onvoldoende":     return "#FF8F8F"; // licht rood
    default: return "#ffffff";
  }
}


/** 
 * 8) Genereer de HTML-tabel.
 *    We vullen een <table> in bij "resultsContent".
 */
function createResultsTable(resultsArr) {
  const container = document.getElementById("resultsContent");
  container.innerHTML = ""; // wis eventueel vorige resultaten

  // Maak <table> (zonder inline-styles, op 1 uitzondering na)
  const table = document.createElement("table");

  // Table head
  const thead = document.createElement("thead");
  thead.innerHTML = `
    <tr>
      <th>Thema - Subthema</th>
      <th>Percentage</th>
      <th>Categorie Label</th>
      <th>Advies</th>
    </tr>
  `;
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  
  resultsArr.forEach(r => {
    const tr = document.createElement("tr");

    // Dynamische achtergrondkleur:
    const bgColor = labelToColor(r.label);
    tr.style.backgroundColor = bgColor;

    // subName
    let tdName = document.createElement("td");
    tdName.textContent = r.subName;
    tr.appendChild(tdName);

    // percentage
    let tdPct = document.createElement("td");
    tdPct.textContent = r.pct + "%";
    tr.appendChild(tdPct);

    // label
    let tdLabel = document.createElement("td");
    tdLabel.textContent = r.label;
    tr.appendChild(tdLabel);

    // advies
    let tdAdvice = document.createElement("td");
    tdAdvice.textContent = r.advice;
    tr.appendChild(tdAdvice);

    tbody.appendChild(tr);
  });

  table.appendChild(tbody);
  container.appendChild(table);
}

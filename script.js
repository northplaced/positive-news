const FI_LABEL = "Suomi";
const ET_LABEL = "Viro";

function formatDate(isoOrRfc822) {
  if (!isoOrRfc822) return "";
  const d = new Date(isoOrRfc822);
  if (isNaN(d.getTime())) return "";
  return d.toLocaleString("fi-FI", {
    day: "numeric",
    month: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function renderEntry(entry) {
  const card = document.createElement("article");
  card.className = "entry-card";

  const outlet = document.createElement("div");
  outlet.className = "entry-outlet";
  outlet.textContent = entry.outlet;
  card.appendChild(outlet);

  const title = document.createElement("a");
  title.className = "entry-title";
  title.href = entry.link;
  title.target = "_blank";
  title.rel = "noopener noreferrer";
  title.textContent = entry.title;
  card.appendChild(title);

  if (entry.summary) {
    const summary = document.createElement("p");
    summary.className = "entry-summary";
    summary.textContent = entry.summary;
    card.appendChild(summary);
  }

  const date = document.createElement("div");
  date.className = "entry-date";
  date.textContent = formatDate(entry.published);
  card.appendChild(date);

  return card;
}

function renderColumn(label, entries) {
  const column = document.createElement("div");
  column.className = "lang-column";

  const heading = document.createElement("h3");
  heading.textContent = label;
  column.appendChild(heading);

  if (entries.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty-note";
    empty.textContent = "Ei tuoreita juttuja juuri nyt.";
    column.appendChild(empty);
    return column;
  }

  for (const entry of entries) {
    column.appendChild(renderEntry(entry));
  }
  return column;
}

function renderCategory(category) {
  const section = document.createElement("section");
  section.className = "category";
  section.dataset.categoryKey = category.key;

  const heading = document.createElement("h2");
  heading.textContent = category.label;
  section.appendChild(heading);

  const grid = document.createElement("div");
  grid.className = "lang-grid";

  const fiEntries = category.entries.filter((e) => e.lang === "fi");
  const etEntries = category.entries.filter((e) => e.lang === "et");

  grid.appendChild(renderColumn(FI_LABEL, fiEntries));
  grid.appendChild(renderColumn(ET_LABEL, etEntries));

  section.appendChild(grid);
  return section;
}

async function loadFeed() {
  const main = document.getElementById("categories");
  const updatedAt = document.getElementById("updated-at");

  try {
    const res = await fetch("data/feed.json", { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    main.innerHTML = "";
    for (const category of data.categories) {
      main.appendChild(renderCategory(category));
    }

    if (data.generated_at) {
      const generated = new Date(data.generated_at);
      updatedAt.textContent = isNaN(generated.getTime())
        ? ""
        : `Päivitetty: ${generated.toLocaleString("fi-FI")}`;
    } else {
      updatedAt.textContent = "Ei vielä päivitetty";
    }
  } catch (err) {
    main.innerHTML = "";
    const notice = document.createElement("p");
    notice.className = "error-note";
    notice.textContent =
      "Uutisia ei juuri nyt saatu ladattua. Kokeile hetken kuluttua uudelleen.";
    main.appendChild(notice);
    updatedAt.textContent = "";
    console.error("Failed to load feed.json", err);
  }
}

loadFeed();

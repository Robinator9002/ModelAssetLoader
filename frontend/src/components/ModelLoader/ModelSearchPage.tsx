// frontend/src/components/ModelLoader/ModelSearchPage.tsx
import React, { useState, useCallback, useEffect, useRef } from "react";
import {
	searchModels,
	getModelDetails, // Hinzugefügt für direkten Download
	type SearchModelParams,
	type HFModelListItem,
	type PaginatedModelListResponse,
	type HFModelDetails, // Hinzugefügt
	type HFModelFile, // Hinzugefügt
} from "../../api/api";
import { Download } from "lucide-react"; // Beispiel Icon

interface ModelSearchPageProps {
	onModelSelect: (model: HFModelListItem) => void;
	openDownloadModal: (
		modelDetails: HFModelDetails,
		specificFile?: HFModelFile
	) => void;
	isConfigurationDone: boolean;
}

const ModelSearchPage: React.FC<ModelSearchPageProps> = ({
	onModelSelect,
	openDownloadModal,
	isConfigurationDone,
}) => {
	const [searchParams, setSearchParams] = useState<SearchModelParams>({
		search: "",
		author: "",
		tags: [],
		sort: "lastModified",
		direction: -1,
		limit: 25,
		page: 1,
	});
	const [results, setResults] = useState<HFModelListItem[]>([]);
	const [isLoading, setIsLoading] = useState<boolean>(false);
	const [isFetchingDetailsForDownload, setIsFetchingDetailsForDownload] =
		useState<string | null>(null); // model.id
	const [error, setError] = useState<string | null>(null);
	const [hasMore, setHasMore] = useState<boolean>(false);
	const [currentPage, setCurrentPage] = useState<number>(1);

	const searchInputRef = useRef<HTMLInputElement>(null);
	const isInitialMount = useRef(true);

	const handleInputChange = (
		e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>
	) => {
		const { name, value } = e.target;
		let newParams = { ...searchParams };

		if (name === "tags") {
			newParams = {
				...newParams,
				[name]: value
					.split(",")
					.map((tag) => tag.trim())
					.filter((tag) => tag),
			};
		} else if (name === "direction" || name === "limit") {
			newParams = { ...newParams, [name]: parseInt(value, 10) };
		} else {
			newParams = { ...newParams, [name]: value };
		}
		if (
			name !== "page" &&
			(name === "search" ||
				name === "author" ||
				name === "tags" ||
				name === "sort" ||
				name === "direction")
		) {
			newParams.page = 1;
		}
		setSearchParams(newParams);
	};

	const performSearch = useCallback(
		async (
			pageToLoad: number,
			isNewSearchDueToFilterChange: boolean = false
		) => {
			setIsLoading(true);
			setError(null);
			if (isNewSearchDueToFilterChange) {
				setResults([]);
				setCurrentPage(1);
				pageToLoad = 1;
			}
			try {
				const currentSearchParams: SearchModelParams = {
					...searchParams,
					page: pageToLoad,
				};
				const response: PaginatedModelListResponse = await searchModels(
					currentSearchParams
				);

				if (pageToLoad === 1 || isNewSearchDueToFilterChange) {
					setResults(response.items);
				} else {
					setResults((prevResults) => [...prevResults, ...response.items]);
				}
				setHasMore(response.has_more);
				setCurrentPage(pageToLoad);
			} catch (err) {
				setError(
					"Fehler bei der Suche nach Modellen. Bitte versuchen Sie es später erneut."
				);
				console.error(err);
			} finally {
				setIsLoading(false);
			}
		},
		[searchParams]
	);

	const handleSearchSubmit = (e?: React.FormEvent<HTMLFormElement>) => {
		if (e) e.preventDefault();
		performSearch(1, true);
	};

	useEffect(() => {
		if (isInitialMount.current) {
			isInitialMount.current = false;
			// Optional: Initialen Suchlauf beim ersten Laden starten, wenn gewünscht
			// performSearch(1, true);
			return;
		}
		if (!isLoading) {
			performSearch(1, true);
		}
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [searchParams.sort, searchParams.direction]);

	const handleLoadMore = () => {
		if (hasMore && !isLoading) {
			performSearch(currentPage + 1);
		}
	};

	const handleDirectDownloadClick = async (
		e: React.MouseEvent,
		model: HFModelListItem
	) => {
		e.stopPropagation(); // Verhindert, dass onModelSelect ausgelöst wird
		if (!isConfigurationDone) {
			alert(
				"Bitte konfigurieren Sie zuerst den Basispfad in den Einstellungen, um Downloads zu ermöglichen."
			);
			return;
		}
		setIsFetchingDetailsForDownload(model.id);
		setError(null);
		try {
			const parts = model.id.split("/");
			if (parts.length < 2) throw new Error("Ungültige Modell-ID.");
			const author = parts[0];
			const modelName = parts.slice(1).join("/");
			const details = await getModelDetails(author, modelName);
			if (details) {
				openDownloadModal(details); // Kein specificFile, Nutzer wählt im Modal
			} else {
				setError(`Details für ${model.id} konnten nicht geladen werden.`);
			}
		} catch (err: any) {
			setError(`Fehler beim Laden der Details für ${model.id}: ${err.message}`);
			console.error(err);
		} finally {
			setIsFetchingDetailsForDownload(null);
		}
	};

	return (
		<div className="model-search-page">
			<div className="search-form-container">
				<form onSubmit={handleSearchSubmit} className="search-form">
					<div className="form-row">
						<input
							ref={searchInputRef}
							type="text"
							name="search"
							placeholder="Modell suchen (z.B. Llama, Stable Diffusion)..."
							value={searchParams.search}
							onChange={handleInputChange}
							className="search-input-main"
						/>
					</div>
					<div className="form-row filter-row">
						<input
							type="text"
							name="author"
							placeholder="Autor/Organisation (z.B. meta-llama)"
							value={searchParams.author}
							onChange={handleInputChange}
							className="search-input-filter"
						/>
						<input
							type="text"
							name="tags"
							placeholder="Tags (kommagetrennt, z.B. text-generation,pytorch)"
							value={searchParams.tags?.join(", ")} // Stellt sicher, dass es ein String ist
							onChange={handleInputChange}
							className="search-input-filter"
						/>
					</div>
					<div className="form-row sort-row">
						<select
							name="sort"
							value={searchParams.sort}
							onChange={handleInputChange}
							className="search-select"
						>
							<option value="lastModified">Neueste</option>
							<option value="downloads">Downloads</option>
							<option value="likes">Likes</option>
							<option value="author">Autor</option>
							<option value="id">ID</option>
						</select>
						<select
							name="direction"
							value={searchParams.direction?.toString()}
							onChange={handleInputChange}
							className="search-select"
						>
							<option value="-1">Absteigend</option>
							<option value="1">Aufsteigend</option>
						</select>
						<button
							type="submit"
							disabled={isLoading && currentPage === 1}
							className="search-button"
						>
							{isLoading && currentPage === 1 ? "Suchen..." : "Suchen"}
						</button>
					</div>
				</form>
			</div>

			{error && <p className="error-message">{error}</p>}

			<div className="search-results-container">
				{results.length > 0 ? (
					<ul className="search-results-list">
						{results.map((model) => (
							<li
								key={model.id}
								className="result-item"
								onClick={() => onModelSelect(model)}
								tabIndex={0}
								onKeyPress={(e) => e.key === "Enter" && onModelSelect(model)}
								title={`Details für ${model.model_name} anzeigen`}
							>
								<div className="result-item-icon">
									{/* Placeholder Icon */}
									<svg
										xmlns="http://www.w3.org/2000/svg"
										width="24"
										height="24"
										viewBox="0 0 24 24"
										fill="currentColor"
										className="model-icon"
									>
										<path d="M20 18c1.1 0 1.99-.9 1.99-2L22 6c0-1.1-.9-2-2-2H4c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2H0v2h24v-2h-4zM4 6h16v10H4V6z"></path>
									</svg>
								</div>
								<div className="result-item-info">
									<h3>{model.model_name}</h3>
									<p className="author-info">
										von: {model.author || "Unbekannt"}
									</p>
									{model.pipeline_tag && (
										<span className="pipeline-tag">{model.pipeline_tag}</span>
									)}
								</div>
								<div className="result-item-stats">
									<span>
										<svg
											viewBox="0 0 24 24"
											width="12"
											height="12"
											fill="currentColor"
											style={{ verticalAlign: "middle", marginRight: "4px" }}
										>
											<path d="M19.5 13.572l-7.5 7.428l-7.5-7.428m0 0A5.009 5.009 0 0 1 12 2.572a5.009 5.009 0 0 1 7.5 11z"></path>
										</svg>
										{model.likes != null ? model.likes.toLocaleString() : "N/A"}
									</span>
									<span>
										<svg
											viewBox="0 0 24 24"
											width="12"
											height="12"
											fill="currentColor"
											style={{ verticalAlign: "middle", marginRight: "4px" }}
										>
											<path d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z"></path>
										</svg>
										{model.downloads != null
											? model.downloads.toLocaleString()
											: "N/A"}
									</span>
									<span>
										{model.lastModified
											? new Date(model.lastModified).toLocaleDateString()
											: "N/A"}
									</span>
								</div>
								<div className="result-item-actions">
									<button
										className="button-icon download-direct-button"
										onClick={(e) => handleDirectDownloadClick(e, model)}
										disabled={
											!isConfigurationDone ||
											isFetchingDetailsForDownload === model.id
										}
										title={
											!isConfigurationDone
												? "Basispfad nicht konfiguriert"
												: `Dateien für ${model.model_name} herunterladen`
										}
									>
										{isFetchingDetailsForDownload === model.id ? (
											<div className="spinner-small"></div>
										) : (
											<Download size={18} />
										)}
									</button>
								</div>
							</li>
						))}
					</ul>
				) : (
					!isLoading && (
						<p className="no-results-message">
							Keine Modelle für Ihre Suche gefunden oder noch keine Suche
							gestartet.
						</p>
					)
				)}

				{isLoading && currentPage > 1 && (
					<p className="loading-message">Lade mehr Modelle...</p>
				)}

				{hasMore && !isLoading && results.length > 0 && (
					<button
						onClick={handleLoadMore}
						disabled={isLoading}
						className="load-more-button"
					>
						Mehr laden
					</button>
				)}
			</div>
		</div>
	);
};

export default ModelSearchPage;

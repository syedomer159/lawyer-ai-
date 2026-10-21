export interface paths {
    "/api/cases": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Cases */
        get: operations["list_cases"];
        put?: never;
        /** Create Case */
        post: operations["create_case"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/cases/{case_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Case */
        get: operations["get_case"];
        put?: never;
        post?: never;
        /** Delete Case */
        delete: operations["delete_case"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/cases/{case_id}/documents": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Documents */
        get: operations["list_documents"];
        put?: never;
        /**
         * Upload Documents
         * @description Store the files and queue ingestion. Identical bytes return the existing document.
         */
        post: operations["upload_documents"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/cases/{case_id}/documents/{doc_id}/pages/{page}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Page */
        get: operations["get_page"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/cases/{case_id}/documents/{doc_id}/pages/{page}/image": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Page Image */
        get: operations["get_page_image"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/cases/{case_id}/search": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Search Case */
        get: operations["search_case"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/cases/{case_id}/usage": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Usage
         * @description Tokens and cost of every LLM call made for this case, by role and model.
         */
        get: operations["get_usage"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/cases/{case_id}/analysis": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Analysis */
        get: operations["get_analysis"];
        put?: never;
        /**
         * Start Analysis
         * @description Run the analysis workflow in the background. Poll GET /analysis for progress.
         */
        post: operations["start_analysis"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/cases/{case_id}/conflicts/{conflict_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Update Conflict */
        patch: operations["update_conflict"];
        trace?: never;
    };
    "/api/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Health */
        get: operations["health"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** Adverse */
        Adverse: {
            /** Id */
            id: number;
            /** Explanation */
            explanation: string;
            /** Citations */
            citations: components["schemas"]["CitationView"][];
        };
        /** Analysis */
        Analysis: {
            job: components["schemas"]["AnalysisJob"] | null;
            /** Parties */
            parties: components["schemas"]["Party"][];
            /** Timeline */
            timeline: components["schemas"]["Claim"][];
            /** Conflicts */
            conflicts: components["schemas"]["Conflict"][];
            /** Elements */
            elements: components["schemas"]["Element"][];
            /** Adverse */
            adverse: components["schemas"]["Adverse"][];
            /** Issues */
            issues: components["schemas"]["Issue"][];
        };
        /** AnalysisJob */
        AnalysisJob: {
            /** Id */
            id: string;
            /**
             * Status
             * @enum {string}
             */
            status: "running" | "done" | "failed";
            /** Step */
            step: string;
            /** Progress */
            progress: number;
            /** Error */
            error: string | null;
            /** Started At */
            started_at: string;
            /** Finished At */
            finished_at: string | null;
        };
        /** Body_upload_documents */
        Body_upload_documents: {
            /** Files */
            files: Blob[];
        };
        /** Case */
        Case: {
            /** Id */
            id: string;
            /** Title */
            title: string;
            /** Client */
            client: string;
            /**
             * User Side
             * @enum {string}
             */
            user_side: "defence" | "prosecution";
            /** Charges */
            charges: string[];
            /** Local Only */
            local_only: boolean;
            /** Embed Model */
            embed_model: string;
            /** Created At */
            created_at: string;
        };
        /** CaseCreate */
        CaseCreate: {
            /** Title */
            title: string;
            /** Client */
            client: string;
            /**
             * User Side
             * @default defence
             * @enum {string}
             */
            user_side: "defence" | "prosecution";
            /** Charges */
            charges?: string[];
            /**
             * Local Only
             * @default false
             */
            local_only: boolean;
        };
        /** ChunkView */
        ChunkView: {
            /** Id */
            id: number;
            /** Bbox */
            bbox: [
                number,
                number,
                number,
                number
            ] | null;
            /** Text */
            text: string;
        };
        /** CitationView */
        CitationView: {
            ref: components["schemas"]["SourceRef"];
            /** Quote */
            quote: string;
            /** Verified */
            verified: boolean;
        };
        /** Claim */
        Claim: {
            /** Id */
            id: number;
            /** Speaker */
            speaker: string;
            /** Aspect */
            aspect: string;
            /** Statement */
            statement: string;
            /** When */
            when: string | null;
            citation: components["schemas"]["CitationView"];
        };
        /** Conflict */
        Conflict: {
            /** Id */
            id: number;
            /** Aspect */
            aspect: string;
            /**
             * Type
             * @enum {string}
             */
            type: "testimony_vs_testimony" | "testimony_vs_document" | "testimony_vs_physical" | "document_vs_document";
            /**
             * Severity
             * @enum {string}
             */
            severity: "high" | "medium" | "low";
            /**
             * Effect
             * @enum {string}
             */
            effect: "helps" | "hurts";
            /** Explanation */
            explanation: string;
            /**
             * Status
             * @enum {string}
             */
            status: "open" | "dismissed";
            /** Claims */
            claims: components["schemas"]["Claim"][];
        };
        /** ConflictUpdate */
        ConflictUpdate: {
            /**
             * Status
             * @enum {string}
             */
            status: "open" | "dismissed";
        };
        /** CrossQuestion */
        CrossQuestion: {
            /** Witness */
            witness: string;
            /** Question */
            question: string;
        };
        /** Document */
        Document: {
            /** Id */
            id: string;
            /** Filename */
            filename: string;
            /**
             * Kind
             * @enum {string}
             */
            kind: "pdf" | "image" | "text";
            /**
             * Status
             * @enum {string}
             */
            status: "queued" | "processing" | "ready" | "failed";
            /** N Pages */
            n_pages: number;
            /** Error */
            error?: string | null;
        };
        /** Element */
        Element: {
            /** Id */
            id: number;
            /**
             * Kind
             * @enum {string}
             */
            kind: "offence" | "procedure";
            /** Element */
            element: string;
            /**
             * Status
             * @enum {string}
             */
            status: "supported" | "weak" | "missing";
            /** Explanation */
            explanation: string;
            /** Citations */
            citations: components["schemas"]["CitationView"][];
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /** HealthResponse */
        HealthResponse: {
            /** Status */
            status: string;
            /** Model Profile */
            model_profile: string;
        };
        /** Issue */
        Issue: {
            /** Id */
            id: number;
            /** Title */
            title: string;
            /** Our Argument */
            our_argument: string;
            /** Opposing Argument */
            opposing_argument: string;
            /** Rebuttal */
            rebuttal: string;
            /** Cross Questions */
            cross_questions: components["schemas"]["CrossQuestion"][];
            /** Citations */
            citations: components["schemas"]["CitationView"][];
        };
        /** PageDetail */
        PageDetail: {
            /** Doc Id */
            doc_id: string;
            /** Page */
            page: number;
            /** N Pages */
            n_pages: number;
            /** Ocr */
            ocr: boolean;
            /** Text */
            text: string;
            /** Chunks */
            chunks: components["schemas"]["ChunkView"][];
        };
        /** Party */
        Party: {
            /** Id */
            id: number;
            /** Name */
            name: string;
            /**
             * Role
             * @enum {string}
             */
            role: "accused" | "complainant" | "witness" | "io" | "police" | "doctor" | "panch" | "other";
        };
        /** RoleUsage */
        RoleUsage: {
            /** Role */
            role: string;
            /** Model */
            model: string;
            /** Calls */
            calls: number;
            /** Input Tokens */
            input_tokens: number;
            /** Output Tokens */
            output_tokens: number;
            /** Cost Usd */
            cost_usd: number;
            /** Unpriced Calls */
            unpriced_calls: number;
        };
        /** SearchHit */
        SearchHit: {
            ref: components["schemas"]["SourceRef"];
            /** Text */
            text: string;
            /** Score */
            score: number;
        };
        /**
         * SourceRef
         * @description Where a piece of text lives in the case. Every citation resolves to one of these.
         */
        SourceRef: {
            /** Chunk Id */
            chunk_id: number;
            /** Doc Id */
            doc_id: string;
            /** Filename */
            filename: string;
            /** Page */
            page: number;
            /** Bbox */
            bbox: [
                number,
                number,
                number,
                number
            ] | null;
        };
        /** UsageSummary */
        UsageSummary: {
            /** Calls */
            calls: number;
            /** Input Tokens */
            input_tokens: number;
            /** Output Tokens */
            output_tokens: number;
            /** Cost Usd */
            cost_usd: number;
            /** By Role */
            by_role: components["schemas"]["RoleUsage"][];
        };
        /** ValidationError */
        ValidationError: {
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
            /** Input */
            input?: unknown;
            /** Context */
            ctx?: Record<string, never>;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    list_cases: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Case"][];
                };
            };
        };
    };
    create_case: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CaseCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Case"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_case: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                case_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Case"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_case: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                case_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_documents: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                case_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Document"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    upload_documents: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                case_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": components["schemas"]["Body_upload_documents"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Document"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_page: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                doc_id: string;
                page: number;
                case_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PageDetail"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_page_image: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                doc_id: string;
                page: number;
                case_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    search_case: {
        parameters: {
            query: {
                q: string;
                k?: number;
            };
            header?: never;
            path: {
                case_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SearchHit"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_usage: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                case_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UsageSummary"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_analysis: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                case_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Analysis"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    start_analysis: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                case_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalysisJob"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_conflict: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                conflict_id: number;
                case_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ConflictUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    health: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HealthResponse"];
                };
            };
        };
    };
}

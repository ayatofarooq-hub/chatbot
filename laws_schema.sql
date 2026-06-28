--
-- PostgreSQL database dump
--

\restrict Zxa1PdP0mgAcnpeDKhnKQcVpzpBnNe7wbZSGCZOsGDItkRnkSRpYVo7ouGKauQV

-- Dumped from database version 17.6
-- Dumped by pg_dump version 17.6

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: iraqi_laws; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.iraqi_laws (
    id integer NOT NULL,
    classification character varying(100) NOT NULL,
    law_number character varying(20),
    law_year smallint,
    article_number character varying(20),
    law_name text NOT NULL,
    summary text
);


--
-- Name: iraqi_laws_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.iraqi_laws_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: iraqi_laws_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.iraqi_laws_id_seq OWNED BY public.iraqi_laws.id;


--
-- Name: iraqi_laws id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.iraqi_laws ALTER COLUMN id SET DEFAULT nextval('public.iraqi_laws_id_seq'::regclass);


--
-- Name: iraqi_laws iraqi_laws_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.iraqi_laws
    ADD CONSTRAINT iraqi_laws_pkey PRIMARY KEY (id);


--
-- PostgreSQL database dump complete
--

\unrestrict Zxa1PdP0mgAcnpeDKhnKQcVpzpBnNe7wbZSGCZOsGDItkRnkSRpYVo7ouGKauQV


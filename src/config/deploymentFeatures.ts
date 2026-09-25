import { parse } from "yaml";
import raw from "../../config/deployment-features.yaml?raw";

export type DeploymentFeatures = {
  accountAggregatorEnabled: boolean;
  externalConnectorsEnabled: boolean;
};

export const DEPLOYMENT_FEATURES = parse(raw) as DeploymentFeatures;
